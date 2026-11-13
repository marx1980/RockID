import csv
from dataclasses import replace

from services.curation.ood_set import build
from services.ingestion.candidates import write_candidates
from tests.test_promote_v2 import _cand


def _c(i, group, author, lic="CC BY 4.0"):
    return replace(_cand(i, f"ood.{group}"), author=author, source_name="Wikimedia Commons", license=lic)


def test_ood_photographers_never_split_and_truth_is_unknown(tmp_path):
    cands = [_c(i, "man_made", f"P{i // 3}") for i in range(30)] + [_c(100, "other_rock", "NC", "CC BY-NC 4.0")]
    write_candidates(tmp_path / "c.csv", cands)
    with (tmp_path / "d.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate_id", "taxon_id", "decision", "reason"])
        for c in cands:
            w.writerow([c.candidate_id, c.taxon_id, "approve_ood", ""])
    report = build(tmp_path / "c.csv", tmp_path / "d.csv", tmp_path / "cal.csv", tmp_path / "test.csv")
    cal = list(csv.DictReader((tmp_path / "cal.csv").open()))
    test = list(csv.DictReader((tmp_path / "test.csv").open()))
    assert {r["ground_truth_id"] for r in cal + test} == {"UNKNOWN"}
    assert not ({r["author"] for r in cal} & {r["author"] for r in test})
    assert report["dropped_for_licence"] == 1 and len(cal) + len(test) == 30
    assert abs(len(cal) - len(test)) <= 3
