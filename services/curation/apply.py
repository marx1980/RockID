"""Turn the agent review into decisions.json (main) and the challenge manifest (vault branch).

  python -m services.curation.apply data_manifests/candidates/candidates.csv \
      data_manifests/candidates/agent_review.csv data_manifests/candidates/decisions.json /path/to/challenge.csv
"""
import csv
import sys
from pathlib import Path

from services.curation.split import split
from services.ingestion.candidates import read_candidates
from services.ingestion.decisions import save_decisions, validate_decisions

CHALLENGE_COLUMNS = ["case_id", "candidate_id", "ground_truth_id", "specimen_id", "source_name", "source_url",
                     "media_url", "author", "license"]


def apply(candidates_csv, review_csv, decisions_out, challenge_out, challenge_fraction=0.25):
    cands = read_candidates(candidates_csv)
    with Path(review_csv).open(newline="", encoding="utf-8") as fh:
        review = {r["candidate_id"]: r["decision"] for r in csv.DictReader(fh)}
    approved = {k for k, v in review.items() if v in ("approve_train", "approve_reference")}
    res = split(cands, approved, challenge_fraction=challenge_fraction)
    decisions = {}
    for cid, d in review.items():
        decisions[cid] = "reserve" if res.assignment.get(cid) == "challenge" else d
    problems = validate_decisions(cands, decisions)
    if problems:
        raise ValueError(problems[:5])
    save_decisions(decisions_out, decisions)
    by_id = {c.candidate_id: c for c in cands}
    rows = []
    for n, cid in enumerate(sorted(k for k, v in res.assignment.items() if v == "challenge"), start=1):
        c = by_id[cid]
        rows.append({"case_id": f"c{n:04d}", "candidate_id": cid, "ground_truth_id": c.taxon_id,
                     "specimen_id": c.specimen_hint, "source_name": c.source_name, "source_url": c.source_url,
                     "media_url": c.media_url, "author": c.author, "license": c.license})
    Path(challenge_out).parent.mkdir(parents=True, exist_ok=True)
    with Path(challenge_out).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CHALLENGE_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return res


if __name__ == "__main__":
    r = apply(*sys.argv[1:5])
    print({"reference": sum(v == "reference" for v in r.assignment.values()),
           "challenge": sum(v == "challenge" for v in r.assignment.values()), "no_challenge": r.no_challenge})
