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
from services.ingestion.leakage import AssetRecord, fingerprint_bytes, find_split_leakage, min_phash_distance


def run(reference_csv, out_json, challenge_csvs, client, delay=0.25) -> dict:
    with Path(reference_csv).open(newline="", encoding="utf-8") as fh:
        reference = [AssetRecord(r["asset_id"], r["specimen_id"], r["source_url"], r["sha256"], r["phash"]) for r in csv.DictReader(fh)]
    challenge, failed = [], []
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
                challenge.append(AssetRecord(r["case_id"], r["specimen_id"], r["source_url"], fp.sha256, fp.phash, fp.phash_variants))
                time.sleep(delay)
    findings = find_split_leakage(reference, challenge)
    nearest = {}
    for c in challenge:
        nearest[c.asset_id] = min((min_phash_distance(c.fingerprint, r.fingerprint), r.asset_id) for r in reference)
    report = {"challenge_checked": len(challenge), "not_fetched": failed,
              "by_reason": dict(Counter(f.reason for f in findings)),
              "findings": [[f.reason, f.challenge_asset, f.reference_asset] for f in findings],
              "nearest_phash_distance_histogram": dict(sorted(Counter(min(d, 20) for d, _ in nearest.values()).items()))}
    Path(out_json).write_text(json.dumps(report, indent=1))
    return report


if __name__ == "__main__":
    with httpx.Client(follow_redirects=True) as client:
        rep = run(sys.argv[1], sys.argv[2], sys.argv[3:], client)
    print({k: v for k, v in rep.items() if k != "findings"})
