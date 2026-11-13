import csv
import json
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

from services.curation.challenge_leakage import run
from services.ingestion.leakage import fingerprint_bytes


def _img(seed):
    im = Image.new("RGB", (64, 64), (200, 200, 200))
    d = ImageDraw.Draw(im)
    for k in range(5):
        d.rectangle([seed * 3 + k * 6, k * 9, seed * 3 + k * 6 + 14, k * 9 + 20], fill=(seed * 20 % 255, 30 * k, 90))
    b = BytesIO(); im.save(b, "JPEG"); return b.getvalue()


def test_flags_near_duplicate_and_passes_distinct(tmp_path):
    ref_raw = _img(1)
    fp = fingerprint_bytes(ref_raw)
    with (tmp_path / "ref.csv").open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["asset_id", "specimen_id", "source_url", "sha256", "phash", "media_url"])
        w.writerow(["r1", "s-ref", "https://x/ref", fp.sha256, fp.phash, "https://img/same.jpg"])
    with (tmp_path / "ch.csv").open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["case_id", "specimen_id", "source_url", "media_url"])
        w.writerow(["c1", "s-a", "https://x/a", "https://img/same.jpg"])
        w.writerow(["c2", "s-b", "https://x/b", "https://img/other.jpg"])
    files = {"https://img/same.jpg": ref_raw, "https://img/other.jpg": _img(9)}
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=files[str(r.url)])))
    rep = run(tmp_path / "ref.csv", tmp_path / "o.json", [tmp_path / "ch.csv"], client, delay=0)
    assert rep["challenge_checked"] == 2 and rep["by_reason"].get("exact_duplicate") == 1
    assert json.loads((tmp_path / "o.json").read_text())["challenge_checked"] == 2
