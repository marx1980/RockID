"""Turn human-approved candidates into reference manifest rows: download, fingerprint, validate.

  python -m services.ingestion.promote data_manifests/candidates/candidates.csv \
      --manifest data_manifests/reference/reference.csv --images data/images

Licence policy is re-checked here, so an approval cannot exceed what the licence allows.
Images are not stored by default (re-fetched from media_url, sha256 verified); --images keeps a local copy.
"""
import argparse
import csv
import sys
import time
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from services.ingestion.candidates import read_candidates
from services.ingestion.decisions import DECISION_TO_USAGE, apply_decisions, load_decisions
from services.ingestion.leakage import fingerprint_bytes, min_phash_distance, Fingerprint
from services.ingestion.licence import permits
from services.ingestion.manifest import REFERENCE_COLUMNS, validate_rows
from services.ingestion.http import get_with_backoff

# Stricter than the review threshold (leakage.DEFAULT_PHASH_THRESHOLD = 8): textured rock photos on
# plain backgrounds are often alike, and an automatic drop must not remove genuinely different photos.
# Uncalibrated; tune on the real corpus.
QUARANTINE_PHASH_DISTANCE = 4
QUARANTINE_COLUMNS = ["asset_id", "taxon_id", "matched_asset_id", "phash_distance", "reason"]


@dataclass
class PromoteResult:
    promoted: int = 0
    skipped_unreviewed: int = 0
    rejected_by_reviewer: int = 0
    reserved: int = 0
    refused_licence: int = 0
    duplicates: int = 0
    quarantined: int = 0
    failed_download: int = 0
    invalid: int = 0


def _existing(manifest: Path) -> list[dict[str, str]]:
    if not manifest.exists():
        return []
    with manifest.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def promote(
    client: httpx.Client, candidates_csv: str | Path, manifest: str | Path, images_dir: str | Path | None,
    retrieval_date: str | None = None, log=lambda *_: None, decisions_path: str | Path | None = None,
    sleep=time.sleep,
) -> PromoteResult:
    """images_dir=None downloads only to fingerprint and verify; nothing is stored."""
    manifest = Path(manifest)
    images_dir = Path(images_dir) if images_dir else None
    if images_dir:
        images_dir.mkdir(parents=True, exist_ok=True)
    rows = _existing(manifest)
    fingerprints: dict[str, Fingerprint] = {}  # asset_id -> fingerprint, for assets promoted this run
    quarantine: list[dict[str, str]] = []
    known_assets = {r["asset_id"] for r in rows}
    known_sha = {r["sha256"] for r in rows}
    res = PromoteResult()
    day = retrieval_date or date.today().isoformat()

    for c in apply_decisions(read_candidates(candidates_csv), load_decisions(decisions_path)):
        if c.candidate_id in known_assets:
            continue
        if not c.review_decision:
            res.skipped_unreviewed += 1
            continue
        if c.review_decision == "reject":
            res.rejected_by_reviewer += 1
            continue
        if c.review_decision == "reserve":
            res.reserved += 1
            continue
        usage = DECISION_TO_USAGE[c.review_decision]
        if not permits(c.license, usage):
            res.refused_licence += 1
            log(f"refused {c.candidate_id}: licence {c.license!r} does not permit {usage}")
            continue
        try:
            resp = get_with_backoff(client, c.media_url, sleep=sleep)
            if resp is None:
                raise RuntimeError("gave up after retries")
            resp.raise_for_status()
            raw = resp.content
            with Image.open(BytesIO(raw)) as im:
                im.verify()
        except Exception as e:  # network, HTTP or decode failure
            res.failed_download += 1
            log(f"download failed {c.candidate_id}: {e}")
            continue
        fp = fingerprint_bytes(raw)
        if fp.sha256 in known_sha:
            res.duplicates += 1
            continue
        near = next((aid for aid, other in fingerprints.items()
                     if min_phash_distance(fp, other) <= QUARANTINE_PHASH_DISTANCE), None)
        if near:
            res.quarantined += 1
            quarantine.append({"asset_id": c.candidate_id, "taxon_id": c.taxon_id, "matched_asset_id": near,
                               "phash_distance": str(min_phash_distance(fp, fingerprints[near])),
                               "reason": "near_duplicate_image"})
            continue
        row = {
            "asset_id": c.candidate_id, "taxon_id": c.taxon_id, "specimen_id": c.specimen_hint,
            "source_name": c.source_name, "source_url": c.source_url or c.media_url, "author": c.author,
            "license": c.license, "retrieval_date": day, "usage_decision": usage,
            "sha256": fp.sha256, "phash": fp.phash, "media_url": c.media_url,
        }
        if validate_rows([row]):
            res.invalid += 1
            log(f"invalid {c.candidate_id}: {validate_rows([row])}")
            continue
        if images_dir:
            (images_dir / f"{fp.sha256}.jpg").write_bytes(raw)
        fingerprints[c.candidate_id] = fp
        rows.append(row)
        known_assets.add(c.candidate_id)
        known_sha.add(fp.sha256)
        res.promoted += 1

    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REFERENCE_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    if quarantine:
        qpath = manifest.with_name("quarantine.csv")
        known = []
        if qpath.exists():
            with qpath.open(newline="", encoding="utf-8") as fh:
                known = list(csv.DictReader(fh))
        seen = {r["asset_id"] for r in known}
        with qpath.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=QUARANTINE_COLUMNS)
            w.writeheader()
            w.writerows(known + [q for q in quarantine if q["asset_id"] not in seen])
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--manifest", default="data_manifests/reference/reference.csv")
    ap.add_argument("--images", default=None, help="store downloaded images here (default: do not store)")
    ap.add_argument("--decisions", default="data_manifests/candidates/decisions.json")
    a = ap.parse_args(argv)
    with httpx.Client(follow_redirects=True) as client:
        res = promote(client, a.candidates, a.manifest, a.images, log=lambda m: print(m, file=sys.stderr),
                      decisions_path=a.decisions)
    print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
