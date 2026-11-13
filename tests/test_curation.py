import json
from io import BytesIO

import httpx
from PIL import Image

from services.curation.contact_sheet import PER_SHEET, build, thumb_url
from services.ingestion.candidates import write_candidates
from tests.test_promote_v2 import _cand


def test_thumb_urls():
    assert thumb_url("https://ids.si.edu/ids/deliveryService?id=X&max=1024") == "https://ids.si.edu/ids/deliveryService?id=X&max=330"
    assert thumb_url("https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/F.jpg/1024px-F.jpg") == \
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/F.jpg/330px-F.jpg"
    assert thumb_url("https://upload.wikimedia.org/wikipedia/commons/a/ab/F.jpg?utm=x") == \
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/F.jpg/330px-F.jpg"


def test_sheets_index_and_missing(tmp_path):
    cands = [_cand(i, "min.quartz", review="") for i in range(PER_SHEET + 3)]
    cands.append(_cand(999, "min.calcite", review=""))
    csv = tmp_path / "c.csv"
    write_candidates(csv, cands)
    buf = BytesIO()
    Image.new("RGB", (300, 200), (90, 90, 90)).save(buf, "JPEG")

    def handler(req):
        return httpx.Response(404) if "/5.jpg" in str(req.url) else httpx.Response(200, content=buf.getvalue())

    res = build(csv, tmp_path / "s", httpx.Client(transport=httpx.MockTransport(handler)), workers=2, commons_delay=0)
    assert res == {"sheets": 3, "candidates": PER_SHEET + 4, "missing": 1}
    index = json.loads((tmp_path / "s/index.json").read_text())
    assert index["min.quartz-2"] == {str(PER_SHEET + k + 1): f"t:{PER_SHEET + k}" for k in range(3)} or len(index["min.quartz-2"]) == 3
    assert json.loads((tmp_path / "s/missing.json").read_text()) == ["t:5"]
    assert (tmp_path / "s/min.calcite-1.jpg").exists() and "| min.calcite-1 | 1 |" in (tmp_path / "s/ATTRIBUTION.md").read_text()


def test_fetch_retries_on_429():
    from services.curation.contact_sheet import fetch
    buf = BytesIO()
    Image.new("RGB", (50, 50)).save(buf, "PNG")
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "0"}) if len(calls) < 3 else httpx.Response(200, content=buf.getvalue())

    im = fetch(httpx.Client(transport=httpx.MockTransport(handler)), _cand(1, review=""), sleep=lambda s: None)
    assert im is not None and len(calls) == 3


def test_later_round_skips_reviewed_and_prefixes_sheets(tmp_path):
    from services.curation.contact_sheet import build, reviewed_ids
    from services.ingestion.candidates import write_candidates
    import csv, httpx
    from io import BytesIO
    from PIL import Image

    def cand(i):
        from services.ingestion.candidates import Candidate
        return Candidate(f"x:{i}", "rock.marble", "S", str(i), "t", "u", f"https://img.test/{i}.jpg", "a", "CC BY 4.0", "", f"x:{i}", "high", True, "", "allowed_reference_only", "", "")

    buf = BytesIO(); Image.new("RGB", (40, 40), (120, 120, 120)).save(buf, "JPEG")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=buf.getvalue())))
    write_candidates(tmp_path / "c.csv", [cand(1), cand(2), cand(3)])
    (tmp_path / "r.csv").write_text("candidate_id,taxon_id,decision,reason,reviewer,sheet,tile\nx:1,rock.marble,approve_reference,ok,a,s,1\n")
    res = build(tmp_path / "c.csv", tmp_path / "out", client, skip=reviewed_ids(tmp_path / "r.csv"), prefix="r2-")
    assert res["candidates"] == 2
    assert (tmp_path / "out" / "r2-rock.marble-1.jpg").exists()
    import json
    assert set(json.loads((tmp_path / "out" / "index.json").read_text())["r2-rock.marble-1"].values()) == {"x:2", "x:3"}


def test_merge_round_keeps_challenge_frozen_and_blocks_overlap(tmp_path):
    import csv, json
    from services.curation.merge_round import merge_round
    from services.ingestion.candidates import Candidate, write_candidates

    def cand(i, author, spec):
        return Candidate(f"x:{i}", "rock.granite", "Museum", str(i), "t", f"https://m/{i}", f"https://img/{i}.jpg", author, "CC BY 4.0", "", spec, "high", True, "", "allowed_reference_only", "", "")

    write_candidates(tmp_path / "c.csv", [cand(1, "Ann", "sp1"), cand(2, "Bob", "sp2"), cand(3, "Museum", "sp3"), cand(4, "Cy", "sp4")])
    with (tmp_path / "r.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate_id", "taxon_id", "decision", "reason", "reviewer", "sheet", "tile"])
        for i, d in ((1, "approve_reference"), (2, "approve_reference"), (3, "approve_reference"), (4, "reject")):
            w.writerow([f"x:{i}", "rock.granite", d, "r", "a", "s", i])
    (tmp_path / "d.json").write_text(json.dumps({"x:4": "approve_reference"}))  # already decided: untouched
    with (tmp_path / "v.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "candidate_id", "ground_truth_id", "specimen_id", "source_name", "source_url", "media_url", "author", "license"])
        w.writerow(["c1", "y:1", "rock.granite", "spZ", "Museum", "https://other/1", "u", "Ann", "CC BY 4.0"])  # same photographer as x:1
    res = merge_round(tmp_path / "c.csv", tmp_path / "r.csv", tmp_path / "d.json", tmp_path / "v.csv")
    out = json.loads((tmp_path / "d.json").read_text())
    assert out["x:1"] == "reject" and out["x:2"] == "approve_reference" and out["x:3"] == "approve_reference"
    assert out["x:4"] == "approve_reference" and res["conflicts"][0][0] == "x:1"
    assert "reserve" not in out.values()


def test_reinstate_polished_sets_form_caps_and_respects_challenge(tmp_path):
    import csv, json
    from services.curation.forms import reinstate_polished
    from services.ingestion.candidates import Candidate, write_candidates

    def cand(i, author, usage="allowed_reference_only"):
        return Candidate(f"x:{i}", "rock.marble", "Museum", str(i), "t", f"https://m/{i}", f"https://img/{i}.jpg", author, "CC BY 4.0", "", f"sp{i}", "high", True, "", usage, "", "")

    ids = list(range(1, 8))
    write_candidates(tmp_path / "c.csv", [cand(i, "Ann" if i == 1 else "Museum") for i in ids])
    with (tmp_path / "r.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate_id", "taxon_id", "decision", "reason", "reviewer", "sheet", "tile"])
        for i in ids:
            w.writerow([f"x:{i}", "rock.marble", "reject", "cut_gemstone" if i == 7 else "polished_slab_scan", "a", "s", i])
    (tmp_path / "d.json").write_text(json.dumps({f"x:{i}": "reject" for i in ids}))
    (tmp_path / "f.json").write_text("{}")
    with (tmp_path / "v.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "candidate_id", "ground_truth_id", "specimen_id", "source_name", "source_url", "media_url", "author", "license"])
        w.writerow(["c1", "y:1", "rock.marble", "spZ", "Museum", "https://other/1", "u", "Ann", "CC BY 4.0"])
    res = reinstate_polished(tmp_path / "c.csv", tmp_path / "r.csv", tmp_path / "d.json", tmp_path / "f.json", tmp_path / "v.csv", cap=3)
    d, f = json.loads((tmp_path / "d.json").read_text()), json.loads((tmp_path / "f.json").read_text())
    approved = [k for k, v in d.items() if v == "approve_reference"]
    assert len(approved) == 3 and set(approved) == set(f) and set(f.values()) == {"polished"}
    assert d["x:1"] == "reject" and d["x:7"] == "reject"  # challenge photographer, faceted gem
    assert res == {"reinstated": 3, "left_out_by_cap": 2}


def test_promote_writes_form_and_defaults_old_rows_to_natural(tmp_path):
    import csv, json
    from services.ingestion.candidates import write_candidates
    from services.ingestion.manifest import validate_file
    from services.ingestion.promote import promote
    from tests.test_harvest import _jpeg

    a, b = _cand(1), _cand(2)
    write_candidates(tmp_path / "c.csv", [a, b])
    (tmp_path / "f.json").write_text(json.dumps({"t:2": "tumbled"}))
    m = tmp_path / "ref.csv"
    promote(_client_files({a.media_url: _jpeg(1), b.media_url: _jpeg(2)}), tmp_path / "c.csv", m, None, retrieval_date="2026-11-13", forms_path=tmp_path / "f.json")
    forms = {r["asset_id"]: r["form"] for r in csv.DictReader(m.open())}
    assert forms == {"t:1": "natural", "t:2": "tumbled"} and validate_file(m) == []


def _client_files(files):
    from tests.test_promote_v2 import _client
    return _client(files)
