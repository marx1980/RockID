"""Bring photos rejected only for being polished or cut back in, labelled with their form.

Policy change (2026-11-13): the app should identify polished and tumbled stones too, so a photo whose
only fault was `polished_slab_scan` or `polished_or_cut` is a legitimate reference photo of form
"polished". Faceted gems (`cut_gemstone`) stay out. Large single-collection scan sets are capped
per taxon so one backdrop cannot dominate a class. Same leakage rule as any later round: a photo that
shares a photographer, specimen or source page with a challenge case of that taxon stays rejected.

  python -m services.curation.forms candidates.csv agent_review.csv decisions.json forms.json [challenge.csv]
"""
import csv
import hashlib
import sys
from pathlib import Path

from services.curation.merge_round import _author
from services.curation.split import _page
from services.ingestion.candidates import read_candidates
from services.ingestion.decisions import load_decisions, load_forms, save_decisions, save_forms, validate_decisions

REASONS = {"polished_slab_scan", "polished_or_cut"}
CAP_PER_TAXON_SOURCE = 60  # same-source polished photos kept per taxon (NHM scans are 140+ per taxon)


def _key(cid: str) -> str:
    return hashlib.sha1(cid.encode()).hexdigest()


def reinstate_polished(candidates_csv, review_csv, decisions_path, forms_path, challenge_csv=None, cap=CAP_PER_TAXON_SOURCE) -> dict:
    cands = {c.candidate_id: c for c in read_candidates(candidates_csv)}
    decisions, forms = load_decisions(decisions_path), load_forms(forms_path)
    with Path(review_csv).open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["reason"] in REASONS and r["decision"] == "reject"]
    blocked: dict[str, set[str]] = {}
    if challenge_csv:
        with Path(challenge_csv).open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                a = _author(r["author"], r["source_name"])
                blocked.setdefault(r["ground_truth_id"], set()).update(
                    {f"s:{r['specimen_id']}", f"p:{_page(r['source_url'])}"} | ({f"a:{a}"} if a else set()))
    groups: dict[tuple[str, str], list[str]] = {}
    seen: set[str] = set()
    for r in rows:
        cid = r["candidate_id"]
        c = cands.get(cid)
        if c is None or cid in seen or c.proposed_usage == "rejected" or decisions.get(cid) != "reject":
            continue
        seen.add(cid)
        keys = {f"s:{c.specimen_hint}", f"p:{_page(c.source_url)}"} | ({f"a:{_author(c.author, c.source_name)}"} if _author(c.author, c.source_name) else set())
        if keys & blocked.get(c.taxon_id, set()):
            continue
        groups.setdefault((c.taxon_id, c.source_name), []).append(cid)
    added, capped = {}, 0
    for (_taxon, _src), ids in groups.items():
        ids.sort(key=_key)
        capped += max(0, len(ids) - cap)
        for cid in ids[:cap]:
            added[cid] = "approve_reference"
            forms[cid] = "polished"
    merged = {**decisions, **added}
    problems = validate_decisions(list(cands.values()), merged)
    if problems:
        raise ValueError(problems[:5])
    save_decisions(decisions_path, merged)
    save_forms(forms_path, forms)
    return {"reinstated": len(added), "left_out_by_cap": capped}


if __name__ == "__main__":
    print(reinstate_polished(*sys.argv[1:6]))
