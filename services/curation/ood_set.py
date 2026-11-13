"""Build the out-of-distribution (OOD) cases from reviewed OOD candidates.

Every approved OOD photo becomes a case with truth UNKNOWN: the right answer is to abstain. Photos are
grouped into components that share a photographer, specimen or source page (as in split.py, across all
OOD groups) and whole components go to one side: `calibration` (thresholds may be tuned on it) or `test`
(frozen, scored once). OOD photos never enter the reference set.

  python -m services.curation.ood_set ood_candidates.csv decisions_o1.csv out_calibration.csv out_test.csv
"""
import csv
import sys
from pathlib import Path

from services.curation.apply import CHALLENGE_COLUMNS
from services.curation.split import _components, _h
from services.ingestion.candidates import read_candidates

ALLOWED_LICENSES = ("CC0", "PUBLIC DOMAIN", "PDM", "CC BY")


def _licence_ok(lic: str) -> bool:
    u = (lic or "").upper().strip()
    return u.startswith(ALLOWED_LICENSES) and "NC" not in u.split() and "-NC" not in u and " ND" not in u


def build(candidates_csv, decisions_csv, out_calibration, out_test) -> dict:
    cands = {c.candidate_id: c for c in read_candidates(candidates_csv)}
    with Path(decisions_csv).open(newline="", encoding="utf-8") as fh:
        approved = sorted(r["candidate_id"] for r in csv.DictReader(fh) if r["decision"].startswith("approve"))
    items = [cands[i] for i in approved if i in cands and _licence_ok(cands[i].license)]
    comps = sorted(_components(items), key=lambda g: _h("ood" + min(c.candidate_id for c in g)))
    sides = {"calibration": [], "test": []}
    for g in comps:  # whole components, to whichever side is smaller; ties alternate by hash order
        side = min(sides, key=lambda s: (len(sides[s]), s != "calibration"))
        sides[side].extend(g)
    report = {}
    for side, out, prefix in (("calibration", out_calibration, "oc"), ("test", out_test, "ot")):
        cs = sorted(sides[side], key=lambda c: c.candidate_id)
        with Path(out).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=CHALLENGE_COLUMNS + ["ood_group"])
            w.writeheader()
            for n, c in enumerate(cs, start=1):
                w.writerow({"case_id": f"{prefix}{n:04d}", "candidate_id": c.candidate_id, "ground_truth_id": "UNKNOWN",
                            "specimen_id": c.specimen_hint, "source_name": c.source_name, "source_url": c.source_url,
                            "media_url": c.media_url, "author": c.author, "license": c.license, "ood_group": c.taxon_id})
        groups: dict[str, int] = {}
        for c in cs:
            groups[c.taxon_id] = groups.get(c.taxon_id, 0) + 1
        report[side] = {"cases": len(cs), "by_group": groups}
    report["dropped_for_licence"] = len(approved) - len(items)
    report["components"] = len(comps)
    return report


if __name__ == "__main__":
    print(build(*sys.argv[1:5]))
