"""Add a later review round to decisions.json WITHOUT re-splitting.

The challenge set is frozen after its first scoring, so new approvals go to the reference side
only, and only if none of them shares a photographer, specimen or source page with a challenge case
of the same taxon. Rows already decided are left alone.

  python -m services.curation.merge_round data_manifests/candidates/candidates.csv \
      data_manifests/candidates/agent_review.csv data_manifests/candidates/decisions.json \
      /path/to/vault/challenge.csv[,/path/to/vault/challenge_b.csv]
"""
import csv
import sys
from pathlib import Path

from services.curation.split import _page
from services.ingestion.candidates import read_candidates
from services.ingestion.decisions import load_decisions, save_decisions, validate_decisions


def _author(author: str, source: str) -> str:
    a = (author or "").strip()
    return "" if a in ("", source) else a.lower()


def merge_round(candidates_csv, review_csv, decisions_path, challenge_csv=None) -> dict:
    cands = {c.candidate_id: c for c in read_candidates(candidates_csv)}
    decisions = load_decisions(decisions_path)
    with Path(review_csv).open(newline="", encoding="utf-8") as fh:
        review = [r for r in csv.DictReader(fh) if r["candidate_id"] not in decisions]
    challenge = []
    for path in filter(None, str(challenge_csv or "").split(",")):  # several challenge sets: comma-separated paths
        with Path(path).open(newline="", encoding="utf-8") as fh:
            challenge.extend(csv.DictReader(fh))
    blocked: dict[str, set[str]] = {}
    for row in challenge:
        blocked.setdefault(row["ground_truth_id"], set()).update(
            {f"s:{row['specimen_id']}", f"p:{_page(row['source_url'])}"}
            | ({f"a:{_author(row['author'], row['source_name'])}"} if _author(row["author"], row["source_name"]) else set()))
    added: dict[str, str] = {}
    conflicts = []
    for r in review:
        cid, decision = r["candidate_id"], r["decision"]
        c = cands.get(cid)
        if c is None:
            continue
        if decision in ("approve_train", "approve_reference"):
            keys = {f"s:{c.specimen_hint}", f"p:{_page(c.source_url)}"}
            if _author(c.author, c.source_name):
                keys.add(f"a:{_author(c.author, c.source_name)}")
            hit = keys & blocked.get(c.taxon_id, set())
            if hit:
                conflicts.append((cid, sorted(hit)))
                decision = "reject"
        added[cid] = decision
    merged = {**decisions, **added}
    problems = validate_decisions(list(cands.values()), merged)
    if problems:
        raise ValueError(problems[:5])
    save_decisions(decisions_path, merged)
    return {"added": len(added), "approved": sum(v.startswith("approve") for v in added.values()), "conflicts": conflicts}


if __name__ == "__main__":
    print(merge_round(*sys.argv[1:5]))
