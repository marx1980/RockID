import csv
import json
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from services.ingestion.candidates import Candidate, write_candidates
from services.ingestion.manifest import REFERENCE_COLUMNS, check_header, validate_file, validate_rows
from services.ingestion.promote import promote


def _texture(seed):
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 255, (16, 24, 3), dtype=np.uint8)).resize((480, 320), Image.BICUBIC)


def _jpg(img):
    b = BytesIO()
    img.save(b, "JPEG", quality=92)
    return b.getvalue()


def _cand(i, taxon="min.quartz", specimen="s", licence="CC0", usage="allowed_train", review="approve_train"):
    return Candidate(
        candidate_id=f"t:{i}", taxon_id=taxon, source_name="T", source_record_id=str(i), title="quartz",
        source_url=f"https://x/{i}", media_url=f"https://img/{i}.jpg", author="A", license=licence,
        license_url="", specimen_hint=f"{specimen}{i}", specimen_hint_confidence="high", taxon_in_title=True,
        other_taxa_in_title="", proposed_usage=usage, policy_reason="", retrieved_at="2026-11-13T00:00:00+00:00",
        review_decision=review,
    )


def _client(files):
    return httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=files[str(r.url)]) if str(r.url) in files else httpx.Response(404)))


def test_manifest_has_media_url_column_and_requires_it():
    assert "media_url" in REFERENCE_COLUMNS
    assert any("missing column media_url" in p for p in check_header([c for c in REFERENCE_COLUMNS if c != "media_url"]))
    row = {c: "" for c in REFERENCE_COLUMNS}
    row.update(asset_id="a", taxon_id="min.quartz", specimen_id="s", source_name="n", source_url="https://u",
               license="CC0", retrieval_date="2026-11-13", usage_decision="allowed_train",
               sha256="a" * 64, phash="f" * 16, media_url="ftp://bad")
    assert any("media_url" in e.problem for e in validate_rows([row]))


def test_one_specimen_cannot_span_two_taxa():
    base = {c: "" for c in REFERENCE_COLUMNS}
    base.update(source_name="n", source_url="https://u", license="CC0", retrieval_date="2026-11-13",
                usage_decision="allowed_train", media_url="https://m", specimen_id="same")
    rows = [{**base, "asset_id": "a", "taxon_id": "min.quartz", "sha256": "a" * 64, "phash": "f" * 16},
            {**base, "asset_id": "b", "taxon_id": "min.calcite", "sha256": "b" * 64, "phash": "e" * 16}]
    assert any("specimen" in e.problem and "taxa" in e.problem for e in validate_rows(rows))


def test_near_duplicate_goes_to_quarantine_not_manifest(tmp_path):
    a = _texture(1)
    files = {
        "https://img/1.jpg": _jpg(a),
        "https://img/2.jpg": _jpg(a.rotate(90, expand=True)),  # same photo, rotated, different bytes
        "https://img/3.jpg": _jpg(_texture(99)),
    }
    cand = tmp_path / "c.csv"
    write_candidates(cand, [_cand(1), _cand(2), _cand(3)])
    res = promote(_client(files), cand, tmp_path / "ref.csv", None, retrieval_date="2026-11-13")
    assert res.promoted == 2 and res.quarantined == 1
    assert validate_file(tmp_path / "ref.csv") == []
    with (tmp_path / "ref.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert {r["asset_id"] for r in rows} == {"t:1", "t:3"} and rows[0]["media_url"] == "https://img/1.jpg"
    with (tmp_path / "quarantine.csv").open() as fh:
        q = list(csv.DictReader(fh))
    assert q[0]["asset_id"] == "t:2" and q[0]["matched_asset_id"] == "t:1"


def test_images_dir_optional_means_nothing_stored(tmp_path):
    cand = tmp_path / "c.csv"
    write_candidates(cand, [_cand(1)])
    promote(_client({"https://img/1.jpg": _jpg(_texture(5))}), cand, tmp_path / "ref.csv", None, retrieval_date="2026-11-13")
    assert not any(p.suffix == ".jpg" for p in tmp_path.rglob("*"))


def test_decisions_file_is_applied_by_promote(tmp_path):
    cand = tmp_path / "c.csv"
    write_candidates(cand, [_cand(1, review=""), _cand(2, review="")])
    dec = tmp_path / "d.json"
    dec.write_text(json.dumps({"t:1": "approve_train", "t:2": "reject"}))
    files = {"https://img/1.jpg": _jpg(_texture(5)), "https://img/2.jpg": _jpg(_texture(6))}
    res = promote(_client(files), cand, tmp_path / "ref.csv", None, retrieval_date="2026-11-13", decisions_path=dec)
    assert res.promoted == 1 and res.rejected_by_reviewer == 1


def test_promote_retries_throttled_downloads(tmp_path):
    cand = tmp_path / "c.csv"
    write_candidates(cand, [_cand(1)])
    calls = []
    img = _jpg(_texture(8))

    def handler(req):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "0"}) if len(calls) < 3 else httpx.Response(200, content=img)

    res = promote(httpx.Client(transport=httpx.MockTransport(handler)), cand, tmp_path / "r.csv", None,
                  retrieval_date="2026-11-13", sleep=lambda s: None)
    assert res.promoted == 1 and len(calls) == 3
