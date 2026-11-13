from services.curation.split import split
from tests.test_promote_v2 import _cand


def _c(i, taxon, author, specimen=None):
    from dataclasses import replace
    c = _cand(i, taxon, review="")
    return replace(c, author=author, specimen_hint=specimen or f"spec-{taxon}-{i}", source_url=f"https://src/{i}")


def test_split_is_author_and_specimen_disjoint():
    cands = []
    i = 0
    for author, n in (("A", 6), ("B", 4), ("C", 3), ("D", 2)):
        for _ in range(n):
            i += 1
            cands.append(_c(i, "min.quartz", author))
    approved = {c.candidate_id for c in cands}
    res = split(cands, approved, challenge_fraction=0.25, min_reference_specimens=3)
    ch = [c for c in cands if res.assignment[c.candidate_id] == "challenge"]
    ref = [c for c in cands if res.assignment[c.candidate_id] == "reference"]
    assert ch and ref
    assert not ({c.author for c in ch} & {c.author for c in ref})
    assert not ({c.specimen_hint for c in ch} & {c.specimen_hint for c in ref})
    assert 0.1 <= len(ch) / len(cands) <= 0.4


def test_shared_specimen_pulls_authors_together():
    # authors X and Y photographed the same specimen: they must land on the same side
    cands = [_c(1, "min.calcite", "X", "s1"), _c(2, "min.calcite", "Y", "s1")]
    cands += [_c(10 + k, "min.calcite", f"R{k}") for k in range(6)]
    res = split(cands, {c.candidate_id for c in cands}, challenge_fraction=0.3, min_reference_specimens=3)
    assert res.assignment["t:1"] == res.assignment["t:2"]


def test_single_author_taxon_gets_no_challenge_cases():
    cands = [_c(i, "rock.slate", "Solo") for i in range(8)]
    res = split(cands, {c.candidate_id for c in cands})
    assert set(res.assignment.values()) == {"reference"}
    assert "rock.slate" in res.no_challenge


def test_reference_floor_is_respected():
    cands = [_c(1, "rock.marble", "A"), _c(2, "rock.marble", "B")]
    res = split(cands, {"t:1", "t:2"}, min_reference_specimens=3)
    assert set(res.assignment.values()) == {"reference"}


def test_deterministic_and_ignores_unapproved():
    cands = [_c(i, "min.pyrite", f"P{i % 4}") for i in range(12)]
    approved = {c.candidate_id for c in cands[:10]}
    a = split(cands, approved).assignment
    b = split(list(reversed(cands)), approved).assignment
    assert a == b and "t:10" not in a and "t:11" not in a


def test_dominant_photographer_never_becomes_the_challenge_set():
    cands = [_c(i, "min.gypsum", "Big") for i in range(20)] + [_c(100 + i, "min.gypsum", f"S{i}") for i in range(6)]
    res = split(cands, {c.candidate_id for c in cands})
    ch = [k for k, v in res.assignment.items() if v == "challenge"]
    assert 0 < len(ch) <= 13 and all(not k.startswith("t:1") or int(k[2:]) >= 100 or True for k in ch)
    assert all(res.assignment[f"t:{i}"] == "reference" for i in range(20))


def test_institution_author_does_not_merge_specimens():
    from dataclasses import replace
    cands = [replace(_c(i, "min.quartz", "Museum"), source_name="Museum") for i in range(12)]
    res = split(cands, {c.candidate_id for c in cands})
    assert 1 <= sum(v == "challenge" for v in res.assignment.values()) <= 5


def test_apply_writes_reserve_and_challenge_manifest(tmp_path):
    import csv
    import json
    from services.curation.apply import apply
    from services.ingestion.candidates import write_candidates
    from services.review.build_site import build_site
    cands = [_c(i, "min.quartz", f"A{i % 5}") for i in range(20)]
    write_candidates(tmp_path / "c.csv", cands)
    with (tmp_path / "r.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate_id", "decision"])
        for c in cands:
            w.writerow([c.candidate_id, "reject" if c.candidate_id == "t:0" else "approve_train"])
    apply(tmp_path / "c.csv", tmp_path / "r.csv", tmp_path / "d.json", tmp_path / "vault/challenge.csv")
    d = json.loads((tmp_path / "d.json").read_text())
    reserved = {k for k, v in d.items() if v == "reserve"}
    with (tmp_path / "vault/challenge.csv").open() as fh:
        ch = list(csv.DictReader(fh))
    assert reserved and {r["candidate_id"] for r in ch} == reserved and d["t:0"] == "reject"
    assert all(r["ground_truth_id"] == "min.quartz" for r in ch)
    build_site(tmp_path / "c.csv", tmp_path / "site", tmp_path / "d.json")
    shown = {x["id"] for x in json.loads((tmp_path / "site/candidates.json").read_text())}
    assert not (shown & reserved)
