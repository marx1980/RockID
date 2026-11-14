"""Challenge set C: stone pool with global leakage rules, stone review, near-duplicate views, freeze caps,
pre-registered multi-photo scoring, Commons series completion. Spec: docs/CHALLENGE_C.md."""
import csv
import json

import httpx
import numpy as np
import pytest

from services.curation import challenge_c as cc
from services.ingestion.candidates import Candidate, write_candidates
from services.ingestion.leakage import Fingerprint
from services.model import multi_photo as mp

REF_COLS = ["asset_id", "taxon_id", "specimen_id", "source_name", "source_url", "author"]
CH_COLS = ["case_id", "candidate_id", "ground_truth_id", "specimen_id", "source_name", "source_url", "media_url", "author", "license"]


def cand(cid, taxon, author, spec, source="Wikimedia Commons", title="t", other=""):
    return Candidate(cid, taxon, source, cid, title, f"https://p/{cid}", f"https://img/{cid}.jpg", author, "CC BY 4.0", "",
                     spec, "low", True, other, "allowed_reference_only", "", "")


def _csv(path, cols, rows):
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        w.writerows(rows)
    return path


def _setup(tmp_path):
    cands = [
        *(cand(f"a:{v}", "min.quartz", "Ann", "commons:qz-ann") for v in (1, 2, 3)),          # new photographer: eligible
        *(cand(f"b:{v}", "min.quartz", "Bob", "commons:qz-bob") for v in (1, 2)),             # Bob shot calcite for the reference
        *(cand(f"c:{v}", "min.quartz", "Cy", "commons:qz-cy") for v in (1, 2)),               # Cy is in challenge A (other taxon)
        *(cand(f"d:{v}", "min.quartz", "Dee", "commons:qz-dee") for v in (1, 2)),             # Dee approved, not yet promoted
        cand("d:9", "min.pyrite", "Dee", "commons:py-dee"),
        *(cand(f"s:{v}", "min.quartz", "Smithsonian", "si:1", source="Smithsonian") for v in (1, 2)),  # institution: no photographer key
        cand("e:1", "min.quartz", "Eve", "commons:qz-eve"),                                   # one photo: not a stone
        *(cand(f"f:{v}", "min.quartz", "Fay", "commons:qz-fay", other="min.pyrite") for v in (1, 2)),  # names another taxon
    ]
    write_candidates(tmp_path / "c.csv", cands)
    (tmp_path / "d.json").write_text(json.dumps({"d:9": "approve_reference"}))
    _csv(tmp_path / "ref.csv", REF_COLS, [["r1", "min.calcite", "x1", "Wikimedia Commons", "https://p/r1", "Bob"]])
    _csv(tmp_path / "a.csv", CH_COLS, [["c0001", "z", "min.fluorite", "z1", "Wikimedia Commons", "https://p/z", "u", "Cy", "CC0"]])
    return cands


def test_pool_applies_global_leakage_rules(tmp_path):
    _setup(tmp_path)
    rep = cc.pool(tmp_path / "c.csv", tmp_path / "d.json", tmp_path / "ref.csv", tmp_path / "none.csv", tmp_path / "pool.csv", [tmp_path / "a.csv"])
    rows = list(csv.DictReader((tmp_path / "pool.csv").open()))
    stones = {r["stone_id"]: [] for r in rows}
    for r in rows:
        stones[r["stone_id"]].append(r)
    authors = {v[0]["author"] for v in stones.values()}
    assert authors == {"Ann", "Smithsonian"}
    assert rep["dropped"]["shares_key_with_reference_or_vault"] == 3 and rep["dropped"]["other_taxon_in_title"] == 1
    inst = [v for v in stones.values() if v[0]["author"] == "Smithsonian"][0]
    assert {r["institution"] for r in inst} == {"1"}
    ann = [v for v in stones.values() if v[0]["author"] == "Ann"][0]
    assert [r["view"] for r in ann] == ["1", "2", "3"] and ann[0]["stone_id"] == cc.stone_id("min.quartz", "commons:qz-ann", "ann")


def _index(tmp_path, taxon="min.quartz", n_stones=2, n_views=3):
    idx = {f"c-{taxon}-1": {str(s): {"stone_id": f"st{s}", "views": {str(v): f"x{s}:{v}" for v in range(1, n_views + 1)}}
                            for s in range(1, n_stones + 1)}}
    (tmp_path / "index.json").write_text(json.dumps(idx))
    return tmp_path / "index.json"


def test_decide_keeps_listed_views_and_refuses_single_view_stones(tmp_path):
    idx = _index(tmp_path)
    res = cc.decide(idx, tmp_path / "rc.csv", "min.quartz", keep="1", views="1:1,3", reasons="2:not_same_stone")
    rows = list(csv.DictReader((tmp_path / "rc.csv").open()))
    kept = {r["candidate_id"] for r in rows if r["decision"] == "keep"}
    assert kept == {"x1:1", "x1:3"} and res["stones_kept"] == 1
    assert {r["reason"] for r in rows if r["candidate_id"].startswith("x2")} == {"not_same_stone"}
    (tmp_path / "p").mkdir()
    with pytest.raises(ValueError):  # a kept stone needs two usable views
        cc.decide(_index(tmp_path / "p", "min.pyrite"), tmp_path / "rc2.csv", "min.pyrite", keep="1", views="1:2")
    with pytest.raises(ValueError):  # already reviewed
        cc.decide(idx, tmp_path / "rc.csv", "min.quartz", keep="1")


def test_near_duplicate_views_by_phash_and_cosine():
    a = Fingerprint("h1", "ffffffff00000000")
    b = Fingerprint("h2", "ffffffff00000001")  # 1 bit away
    c = Fingerprint("h3", "0f0f0f0f0f0f0f0f")
    v1, v2 = np.array([1.0, 0.0]), np.array([0.96, 0.28])  # cosine 0.96
    assert cc.near_duplicates([("1", a, None), ("2", b, None), ("3", c, None)]) == {"2": "near_duplicate_view_phash"}
    assert cc.near_duplicates([("1", a, v1), ("3", c, v2)]) == {"3": "near_duplicate_view_cosine"}


def _draft(tmp_path, stones):
    """stones: list of (stone_id, taxon, author, institution, n_views, scope)"""
    rows = []
    for sid, taxon, author, inst, n, scope in stones:
        for v in range(1, n + 1):
            rows.append({"case_id": "", "candidate_id": f"{sid}:{v}", "ground_truth_id": taxon, "specimen_id": sid,
                         "source_name": "Smithsonian" if inst else "Wikimedia Commons", "source_url": f"https://p/{sid}/{v}",
                         "media_url": "u", "author": "Smithsonian" if inst else author, "license": "CC0", "stone_id": sid,
                         "view": v, "form": "natural", "institution": int(inst), "scope": scope})
    cc._write(tmp_path / "draft.csv", cc.C_COLUMNS, rows)
    return tmp_path / "draft.csv"


def test_freeze_caps_views_and_photographers_and_marks_reserve(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "FREEZE_MIN_LIVE_STONES", 3)
    monkeypatch.setattr(cc, "FREEZE_MIN_LIVE_CLASSES", 1)
    stones = [(f"ann{i}", "min.quartz", "Ann", False, 7, "live") for i in range(5)]  # Ann: 3 per class at most
    stones += [(f"bob{i}", "min.quartz", "Bob", False, 2, "live") for i in range(2)]
    stones += [("si1", "min.quartz", "", True, 3, "live")]
    draft = _draft(tmp_path, stones)
    (tmp_path / "rep.json").write_text(json.dumps({"drop": {"bob0:2": "near_duplicate_view_phash"}}))
    (tmp_path / "d.json").write_text("{}")
    s = cc.freeze(draft, tmp_path / "rep.json", tmp_path / "d.json", tmp_path / "c.csv")
    rows = list(csv.DictReader((tmp_path / "c.csv").open()))
    by = {}
    for r in rows:
        by.setdefault(r["stone_id"], []).append(r)
    assert sum(sid.startswith("ann") for sid in by) == 3 and "bob0" not in by and "bob1" in by
    assert max(len(v) for v in by.values()) == cc.MAX_VIEWS
    assert rows[0]["case_id"] == "s0001" and s["stones"] == len(by)
    assert set(json.loads((tmp_path / "d.json").read_text()).values()) == {"reserve"}
    assert len(json.loads((tmp_path / "d.json").read_text())) == len(rows)


def test_freeze_gate_refuses_a_tiny_set(tmp_path):
    draft = _draft(tmp_path, [("ann0", "min.quartz", "Ann", False, 3, "live")])
    (tmp_path / "d.json").write_text("{}")
    assert cc.freeze(draft, None, tmp_path / "d.json", tmp_path / "c.csv", dry_run=True)["freeze_ok"] is False
    with pytest.raises(ValueError):
        cc.freeze(draft, None, tmp_path / "d.json", tmp_path / "c.csv")


def test_combination_rules():
    P = np.array([[0.6, 0.4, 0.0], [0.1, 0.5, 0.4], [0.2, 0.45, 0.35]])
    assert mp.combine(P, "mean_prob").argmax() == 1
    assert mp.combine(P, "max_conf").argmax() == 0
    assert mp.combine(P, "vote").argmax() == 1
    q = mp.combine(P, "mean_logprob")
    assert abs(q.sum() - 1) < 1e-9 and q[2] < q[1]  # class 2 has a zero in one view


def test_stone_scoring_and_paired_gain():
    classes = ["a", "b"]
    cases, probs = [], {}
    for s in range(20):  # each stone: one wrong view, two right views -> single 2/3, multi right
        for v, p in enumerate(([0.3, 0.7], [0.8, 0.2], [0.9, 0.1]), start=1):
            cid = f"s{s}v{v}"
            cases.append({"case_id": cid, "stone_id": f"st{s}", "view": v, "ground_truth_id": "a", "scope": "live"})
            probs[cid] = np.array(p)
    cases.append({"case_id": "x", "stone_id": "other", "view": 1, "ground_truth_id": "zz", "scope": "live"})
    res = mp.stones(cases, probs, classes)
    assert len(res) == 20 and res[0]["single_top1"] == pytest.approx(2 / 3) and res[0]["multi_top1"] == 1
    s = mp.summary(res, n_boot=200)
    assert s["top1"]["gain"] == pytest.approx(1 / 3, abs=1e-3) and s["primary_supported"]


def test_thresholds_respect_the_ood_limit():
    ood_p = [np.array([0.95, 0.05])] * 10 + [np.array([0.5, 0.5])] * 10
    ood_sim = [0.6] * 10 + [0.9] * 10
    cv_p = [np.array([0.9, 0.1])] * 30
    cv_sim = [0.8] * 30
    t = mp.choose_thresholds(ood_p, ood_sim, cv_p, cv_sim, [True] * 30)
    assert t["ood_named"] <= mp.MAX_OOD_NAMED and t["cv_correct"] == 30
    assert t["tau_s"] > 0.6 or t["tau_p"] > 0.5


def test_commons_series_keeps_same_author_and_specimen():
    from services.ingestion.sources import commons_series

    assert commons_series.series_prefix("File:Galena-Joplin-Missouri-03.jpg") == "Galena-Joplin-Missouri"

    def page(pid, title, artist):
        return {"pageid": pid, "title": title, "imageinfo": [{"mime": "image/jpeg", "url": f"https://upload.wikimedia.org/{pid}.jpg",
                "descriptionurl": f"https://commons.wikimedia.org/wiki/{title}",
                "extmetadata": {"Artist": {"value": artist}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]}

    body = {"query": {"pages": [page(2, "File:Galena-Joplin-Missouri-04.jpg", "Ann"),
                                page(3, "File:Galena-Joplin-Missouri-05.jpg", "Bob"),
                                page(4, "File:Galena-Joplin-Missouri-quarry.jpg", "Ann")]}}
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=body)

    seed = cand("commons:1", "min.galena", "Ann", "commons:galena-joplin-missouri", title="File:Galena-Joplin-Missouri-03.jpg")
    out = commons_series.search(httpx.Client(transport=httpx.MockTransport(handler)), "min.galena", [seed, seed], ["galena"])
    assert [c.candidate_id for c in out] == ["commons:2"] and len(seen) == 1
    assert seen[0].url.params["gaiprefix"] == "Galena-Joplin-Missouri"


def test_merge_round_blocks_challenge_c_photographer_for_every_taxon(tmp_path):
    from services.curation.merge_round import merge_round

    write_candidates(tmp_path / "c.csv", [cand("x:1", "min.pyrite", "Ann", "sp1"), cand("x:2", "min.pyrite", "Bob", "sp2")])
    _csv(tmp_path / "r.csv", ["candidate_id", "taxon_id", "decision", "reason", "reviewer", "sheet", "tile"],
         [["x:1", "min.pyrite", "approve_reference", "", "", "", ""], ["x:2", "min.pyrite", "approve_reference", "", "", "", ""]])
    (tmp_path / "d.json").write_text("{}")
    _csv(tmp_path / "v.csv", cc.C_COLUMNS, [["s0001", "y", "min.quartz", "q1", "Wikimedia Commons", "https://p/y", "u", "Ann", "CC0", "cs:1", 1, "natural", 0, "live"]])
    merge_round(tmp_path / "c.csv", tmp_path / "r.csv", tmp_path / "d.json", tmp_path / "v.csv")
    out = json.loads((tmp_path / "d.json").read_text())
    assert out == {"x:1": "reject", "x:2": "approve_reference"}


def _img_client():
    from io import BytesIO

    from PIL import Image

    def jpg(seed):
        rng = np.random.default_rng(seed)
        b = BytesIO()
        Image.fromarray(rng.integers(0, 255, (12, 16, 3), dtype=np.uint8)).resize((320, 240)).save(b, "JPEG")
        return b.getvalue()

    imgs = {f"https://img/{k}.jpg": jpg(seed) for k, seed in (("a1", 1), ("a2", 2), ("a3", 1), ("b1", 3), ("b2", 4))}
    return httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=imgs[str(r.url)]) if str(r.url) in imgs else httpx.Response(404))), imgs


def test_sheets_and_runner_check_with_mocked_images(tmp_path):
    client, imgs = _img_client()
    pool = [{"stone_id": sid, "view": v, "candidate_id": f"{sid}{v}", "taxon_id": "min.quartz", "scope": "live", "institution": 0,
             "specimen_id": sid, "source_name": "T", "source_url": f"https://p/{sid}{v}", "media_url": f"https://img/{sid}{v}.jpg",
             "author": "Ann", "license": "CC0", "title": "q"} for sid, n in (("a", 3), ("b", 2)) for v in range(1, n + 1)]
    cc._write(tmp_path / "pool.csv", cc.POOL_COLUMNS, pool)
    res = cc.sheets(tmp_path / "pool.csv", tmp_path / "sheets", client, delay=0)
    idx = json.loads((tmp_path / "sheets" / "index.json").read_text())
    assert res["stones"] == 2 and idx["c-min.quartz-1"]["1"]["views"] == {"1": "a1", "2": "a2", "3": "a3"}
    cc.decide(tmp_path / "sheets" / "index.json", tmp_path / "rc.csv", "min.quartz", keep="1-2")
    cc.draft(tmp_path / "pool.csv", tmp_path / "rc.csv", tmp_path / "draft.csv")
    from services.ingestion.leakage import fingerprint_bytes
    fb = fingerprint_bytes(imgs["https://img/b1.jpg"])
    _csv(tmp_path / "ref.csv", ["asset_id", "sha256", "phash"], [["r", fb.sha256, fb.phash]])  # b1 is a reference photo
    rep = cc.check(tmp_path / "draft.csv", tmp_path / "ref.csv", tmp_path / "rep.json", client, delay=0)
    drop = json.loads((tmp_path / "rep.json").read_text())["drop"]
    assert drop == {"a3": "near_duplicate_view_phash", "b1": "copy_of_reference_or_other_set"} and rep["checked"] == 5
