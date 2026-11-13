import json
from pathlib import Path

import httpx
import pytest

from services.ingestion.candidates import read_candidates, write_candidates
from services.ingestion.decisions import (
    apply_decisions, load_decisions, save_decisions, validate_decisions,
)
from services.ingestion.sources import commons, smithsonian
from services.review.build_site import build_site

FIX = Path(__file__).parent / "fixtures"


def _cands():
    def mk(routes):
        return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=routes)))

    si = smithsonian.search(mk(json.loads((FIX / "smithsonian_azurite.json").read_text())),
                            "min.azurite", "azurite", ["azurite"], 10, "k")
    cm = commons.search(mk(json.loads((FIX / "commons_azurite.json").read_text())),
                        "min.azurite", "azurite", ["azurite"], 10)
    return si + cm


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "d.json"
    assert load_decisions(p) == {}
    save_decisions(p, {"b": "reject", "a": "approve_train"})
    assert list(json.loads(p.read_text())) == ["a", "b"]  # stable order for clean diffs
    assert load_decisions(p) == {"a": "approve_train", "b": "reject"}


def test_apply_overlays_decisions_without_touching_others():
    cands = _cands()
    out = apply_decisions(cands, {cands[0].candidate_id: "approve_train"})
    assert out[0].review_decision == "approve_train"
    assert all(c.review_decision == "" for c in out[1:])


def test_validate_flags_unknown_ids_values_and_licence_overreach():
    cands = _cands()
    si = next(c for c in cands if c.license == "CC0")
    bysa = next(c for c in cands if c.license.startswith("CC BY-SA"))
    nc = next(c for c in cands if c.license.startswith("CC BY-NC"))
    problems = validate_decisions(cands, {
        si.candidate_id: "approve_train",       # ok
        bysa.candidate_id: "approve_reference",  # ok
        "nope": "reject",                        # unknown id
        cands[1].candidate_id: "maybe",          # bad value
    })
    assert len(problems) == 2
    assert any("unknown" in p for p in problems) and any("maybe" in p for p in problems)
    over = validate_decisions(cands, {bysa.candidate_id: "approve_train", nc.candidate_id: "approve_reference"})
    assert len(over) == 2 and all("licence" in p for p in over)


def test_build_site_outputs(tmp_path):
    cands = _cands()
    csv_path = tmp_path / "cand.csv"
    write_candidates(csv_path, cands)
    out = tmp_path / "site"
    build_site(csv_path, out)
    data = json.loads((out / "candidates.json").read_text())
    ids = {d["id"] for d in data}
    rejected = {c.candidate_id for c in cands if c.proposed_usage == "rejected"}
    assert rejected and not (ids & rejected)  # policy-rejected candidates are not shown
    assert set(data[0]) >= {"id", "t", "ti", "u", "m", "a", "l", "sp", "sc", "pu", "ot"}
    specs = [d["sp"] for d in data]
    assert specs == sorted(specs)  # same-specimen photos adjacent
    assert len(json.loads((out / "taxa.json").read_text())) == 21
    assert (out / "index.html").exists()


def test_committed_review_folder_is_current(tmp_path):
    """/review/ is served by GitHub Pages in branch mode; it must match a fresh build."""
    root = Path(__file__).resolve().parents[1]
    build_site(root / "data_manifests/candidates/candidates.csv", tmp_path)
    for name in ("index.html", "candidates.json", "taxa.json"):
        assert (root / "review" / name).read_bytes() == (tmp_path / name).read_bytes(), name
