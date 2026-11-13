"""Check challenge sets against the reference set: exact copies, near-duplicates (pHash, dihedral variants),
same specimen, same source page. Challenge images are downloaded and fingerprinted here; the report holds
case and asset ids only (no taxon labels).

  python -m services.curation.challenge_leakage data_manifests/reference/reference.csv report.json \
      vault/challenge.csv vault/challenge_b.csv
"""
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

from services.ingestion.http import get_with_backoff
from PIL import Image

from services.ingestion.leakage import AssetRecord, fingerprint_bytes, find_split_leakage, min_phash_distance


def _thumb(raw: bytes) -> Image.Image:
    from io import BytesIO
    im = Image.open(BytesIO(raw)).convert("RGB")
    im.thumbnail((300, 300))
    return im


def run(reference_csv, out_json, challenge_csvs, client, delay=0.25, pairs_dir=None) -> dict:
    with Path(reference_csv).open(newline="", encoding="utf-8") as fh:
        ref_rows = list(csv.DictReader(fh))
    reference = [AssetRecord(r["asset_id"], r["specimen_id"], r["source_url"], r["sha256"], r["phash"]) for r in ref_rows]
    ref_url = {r["asset_id"]: r["media_url"] for r in ref_rows}
    challenge, failed, raw_by_case = [], [], {}
    for path in challenge_csvs:
        with Path(path).open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                resp = get_with_backoff(client, r["media_url"], attempts=5, min_interval=0, sleep=time.sleep, timeout=60)
                if resp is None or resp.status_code != 200:
                    failed.append(r["case_id"])
                    continue
                try:
                    fp = fingerprint_bytes(resp.content)
                except Exception:
                    failed.append(r["case_id"])
                    continue
                raw_by_case[r["case_id"]] = resp.content
                challenge.append(AssetRecord(r["case_id"], r["specimen_id"], r["source_url"], fp.sha256, fp.phash, fp.phash_variants))
                time.sleep(delay)
    findings = find_split_leakage(reference, challenge)
    by_case = {c.asset_id: c for c in challenge}
    by_ref = {r.asset_id: r for r in reference}
    dist = {(f.challenge_asset, f.reference_asset): min_phash_distance(by_case[f.challenge_asset].fingerprint, by_ref[f.reference_asset].fingerprint) for f in findings}
    if pairs_dir:
        Path(pairs_dir).mkdir(parents=True, exist_ok=True)
        for f in findings:
            r = get_with_backoff(client, ref_url[f.reference_asset], attempts=4, min_interval=0, sleep=time.sleep, timeout=60)
            if r is None or r.status_code != 200:
                continue
            a, b = _thumb(raw_by_case[f.challenge_asset]), _thumb(r.content)
            sheet = Image.new("RGB", (a.width + b.width + 10, max(a.height, b.height)), (20, 20, 20))
            sheet.paste(a, (0, 0)); sheet.paste(b, (a.width + 10, 0))
            sheet.save(Path(pairs_dir) / f"{f.challenge_asset}__{f.reason}.jpg", quality=80)
            time.sleep(delay)
    nearest = {}
    for c in challenge:
        nearest[c.asset_id] = min((min_phash_distance(c.fingerprint, r.fingerprint), r.asset_id) for r in reference)
    report = {"challenge_checked": len(challenge), "not_fetched": failed,
              "by_reason": dict(Counter(f.reason for f in findings)),
              "findings": [[f.reason, f.challenge_asset, f.reference_asset, dist[(f.challenge_asset, f.reference_asset)]] for f in findings],
              "nearest_phash_distance_histogram": dict(sorted(Counter(min(d, 20) for d, _ in nearest.values()).items()))}
    Path(out_json).write_text(json.dumps(report, indent=1))
    return report


if __name__ == "__main__":
    with httpx.Client(follow_redirects=True) as client:
        rep = run(sys.argv[1], sys.argv[2], sys.argv[3:], client, pairs_dir=str(Path(sys.argv[2]).with_name("leakage_pairs")))
    print({k: v for k, v in rep.items() if k != "findings"})
