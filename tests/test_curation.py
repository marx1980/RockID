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

    res = build(csv, tmp_path / "s", httpx.Client(transport=httpx.MockTransport(handler)), workers=2)
    assert res == {"sheets": 3, "candidates": PER_SHEET + 4, "missing": 1}
    index = json.loads((tmp_path / "s/index.json").read_text())
    assert index["min.quartz-2"] == {str(PER_SHEET + k + 1): f"t:{PER_SHEET + k}" for k in range(3)} or len(index["min.quartz-2"]) == 3
    assert json.loads((tmp_path / "s/missing.json").read_text()) == ["t:5"]
    assert (tmp_path / "s/min.calcite-1.jpg").exists() and "| min.calcite-1 | 1 |" in (tmp_path / "s/ATTRIBUTION.md").read_text()
