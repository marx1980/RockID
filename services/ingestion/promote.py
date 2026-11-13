"""Turn human-approved candidates into reference manifest rows: download, fingerprint, validate.

  python -m services.ingestion.promote data_manifests/candidates/candidates.csv \
      --manifest data_manifests/reference/reference.csv --images data/images

Licence policy is re-checked here, so an approval cannot exceed what the licence allows.
Images are stored by sha256 outside git (data/ is ignored).
"""
import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from services.ingestion.candidates import read_candidates
from services.ingestion.leakage import fingerprint_bytes
from services.ingestion.licence import permits
from services.ingestion.manifest import REFERENCE_COLUMNS, validate_rows
from services.ingestion.sources import USER_AGENT

DECISION_TO_USAGE = {"approve_train": "allowed_train", "approve_reference": "allowed_reference_only"}


@dataclass
class PromoteResult:
    promoted: int = 0
    skipped_unreviewed: int = 0
    rejected_by_reviewer: int = 0
    refused_licence: int = 0
    duplicates: int = 0
    failed_download: int = 0
    invalid: int = 0


def _existing(manifest: Path) -> list[dict[str, str]]:
    if not manifest.exists():
        return []
    with manifest.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def promote(
    client: httpx.Client, candidates_csv: str | Path, manifest: str | Path, images_dir: str | Path,
    retrieval_date: str | None = None, log=lambda *_: None,
) -> PromoteResult:
    manifest, images_dir = Path(manifest), Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    rows = _existing(manifest)
    known_assets = {r["asset_id"] for r in rows}
    known_sha = {r["sha256"] for r in rows}
    res = PromoteResult()
    day = retrieval_date or date.today().isoformat()

    for c in read_candidates(candidates_csv):
        if c.candidate_id in known_assets:
            continue
        if not c.review_decision:
            res.skipped_unreviewed += 1
            continue
        if c.review_decision == "reject":
            res.rejected_by_reviewer += 1
            continue
        usage = DECISION_TO_USAGE[c.review_decision]
        if not permits(c.license, usage):
            res.refused_licence += 1
            log(f"refused {c.candidate_id}: licence {c.license!r} does not permit {usage}")
            continue
        try:
            resp = client.get(c.media_url, headers={"User-Agent": USER_AGENT}, timeout=60)
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
        row = {
            "asset_id": c.candidate_id, "taxon_id": c.taxon_id, "specimen_id": c.specimen_hint,
            "source_name": c.source_name, "source_url": c.source_url or c.media_url, "author": c.author,
            "license": c.license, "retrieval_date": day, "usage_decision": usage,
            "sha256": fp.sha256, "phash": fp.phash,
        }
        if validate_rows([row]):
            res.invalid += 1
            log(f"invalid {c.candidate_id}: {validate_rows([row])}")
            continue
        (images_dir / f"{fp.sha256}.jpg").write_bytes(raw)
        rows.append(row)
        known_assets.add(c.candidate_id)
        known_sha.add(fp.sha256)
        res.promoted += 1

    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REFERENCE_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--manifest", default="data_manifests/reference/reference.csv")
    ap.add_argument("--images", default="data/images")
    a = ap.parse_args(argv)
    with httpx.Client(follow_redirects=True) as client:
        res = promote(client, a.candidates, a.manifest, a.images, log=lambda m: print(m, file=sys.stderr))
    print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
