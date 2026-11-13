"""Build challenge set B from whole held-out photographers of a new review round.

The original challenge set (A) is frozen. Set B exists because A has almost no cases for the weak
classes (marble, chert, slate, biotite, magnetite). For each taxon the approved candidates of the round
are grouped into components that share a photographer, specimen or source page (as in split.py). Whole
components go to B until the target is reached; a component that touches an existing reference photo of
the same taxon is not eligible, so B never shares a photographer, specimen or page with the reference set.

  python -m services.curation.challenge_b candidates.csv decisions.json reference.csv round_ids.txt out_challenge_b.csv
"""
import csv
import sys
from pathlib import Path

from services.curation.apply import CHALLENGE_COLUMNS
from services.curation.split import _components, _h, _page
from services.ingestion.candidates import read_candidates
from services.ingestion.decisions import load_decisions, save_decisions

FRACTION, MIN_CASES, MAX_CASES, MIN_REFERENCE = 0.2, 8, 25, 12


def _keys(author, source, specimen, url):
    a = "" if (author or "").strip() in ("", source) else author.strip().lower()
    return {k for k in (f"a:{a}", f"s:{specimen}", f"p:{_page(url)}") if not k.endswith(":")}


def build(candidates_csv, decisions_path, reference_csv, round_ids, out_csv, existing_challenge_csv=None) -> dict:
    cands = {c.candidate_id: c for c in read_candidates(candidates_csv)}
    decisions = load_decisions(decisions_path)
    taken: dict[str, set[str]] = {}
    with Path(reference_csv).open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            taken.setdefault(r["taxon_id"], set()).update(_keys(r["author"], r["source_name"], r["specimen_id"], r["source_url"]))
    if existing_challenge_csv:
        with Path(existing_challenge_csv).open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                taken.setdefault(r["ground_truth_id"], set()).update(_keys(r["author"], r["source_name"], r["specimen_id"], r["source_url"]))
    approved = [cands[i] for i in sorted(round_ids) if i in cands and decisions.get(i, "").startswith("approve")]
    by_taxon: dict[str, list] = {}
    for c in approved:
        by_taxon.setdefault(c.taxon_id, []).append(c)
    chosen, report = [], {}
    # Old reference photos are outside this round, so a round component that shares a key with them is
    # only eligible if it does not: every component is checked against the existing reference keys.
    reference_keys = {t: set(k) for t, k in taken.items()}
    for taxon, items in sorted(by_taxon.items()):
        target = min(MAX_CASES, max(MIN_CASES, round(FRACTION * len(items))))
        comps = sorted(_components(items), key=lambda comp: _h(taxon + min(c.candidate_id for c in comp)))
        got: list = []
        for comp in comps:
            if len(got) >= target:
                break
            keys = set().union(*(_keys(c.author, c.source_name, c.specimen_hint, c.source_url) for c in comp))
            if keys & reference_keys.get(taxon, set()):
                continue
            if len(items) - len(got) - len(comp) < MIN_REFERENCE:
                continue
            got.extend(comp)
        chosen.extend(got)
        report[taxon] = {"approved": len(items), "challenge_b": len(got)}
    for c in chosen:
        decisions[c.candidate_id] = "reserve"
    save_decisions(decisions_path, decisions)
    rows = [{"case_id": f"b{n:04d}", "candidate_id": c.candidate_id, "ground_truth_id": c.taxon_id,
             "specimen_id": c.specimen_hint, "source_name": c.source_name, "source_url": c.source_url,
             "media_url": c.media_url, "author": c.author, "license": c.license}
            for n, c in enumerate(sorted(chosen, key=lambda c: (c.taxon_id, c.candidate_id)), start=1)]
    with Path(out_csv).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CHALLENGE_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return report


if __name__ == "__main__":
    ids = {ln.strip() for ln in Path(sys.argv[4]).read_text().splitlines() if ln.strip()}
    print(build(sys.argv[1], sys.argv[2], sys.argv[3], ids, sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else None))
