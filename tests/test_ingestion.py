from io import BytesIO

import numpy as np
from PIL import Image

from services.ingestion.leakage import (
    AssetRecord, find_split_leakage, fingerprint_bytes, requires_duplicate_review,
)
from services.ingestion.manifest import check_header, validate_rows


def _png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _texture(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 255, (16, 24, 3), dtype=np.uint8)
    return Image.fromarray(small).resize((240, 160), Image.BICUBIC)


def test_rotated_and_mirrored_copies_are_flagged():
    a = fingerprint_bytes(_png(_texture(1)))
    rotated = fingerprint_bytes(_png(_texture(1).rotate(90, expand=True)))
    mirrored = fingerprint_bytes(_png(_texture(1).transpose(Image.FLIP_LEFT_RIGHT)))
    other = fingerprint_bytes(_png(_texture(2)))
    assert requires_duplicate_review(rotated, a)
    assert requires_duplicate_review(mirrored, a)
    assert not requires_duplicate_review(other, a)


def _rec(aid, spec, url, seed):
    fp = fingerprint_bytes(_png(_texture(seed)))
    return AssetRecord(aid, spec, url, fp.sha256, fp.phash, fp.phash_variants)


def test_split_leakage_catches_same_specimen_and_source():
    ref = [_rec("r1", "spec-A", "https://museum.example/obj/1", 10)]
    chal = [
        _rec("c1", "spec-A", "https://other.example/x", 11),  # different photo, same specimen
        _rec("c2", "spec-B", "https://museum.example/obj/1?img=2", 12),  # same source page
        _rec("c3", "spec-C", "https://field.example/z", 13),  # clean
    ]
    reasons = {(f.challenge_asset, f.reason) for f in find_split_leakage(ref, chal)}
    assert ("c1", "same_specimen") in reasons
    assert ("c2", "same_source_page") in reasons
    assert not [r for r in reasons if r[0] == "c3"]


GOOD = {
    "asset_id": "a1", "taxon_id": "min.quartz", "specimen_id": "s1", "source_name": "Example Museum",
    "source_url": "https://museum.example/1", "author": "J. Doe", "license": "CC0-1.0",
    "retrieval_date": "2026-11-13", "usage_decision": "allowed_train",
    "sha256": "a" * 64, "phash": "f" * 16,
}


def test_manifest_accepts_good_row():
    assert validate_rows([GOOD]) == []


def test_manifest_rejects_bad_rows():
    bad = [
        {**GOOD, "asset_id": "a2", "sha256": "b" * 64, "usage_decision": "pending"},
        {**GOOD, "asset_id": "a3", "sha256": "c" * 64, "taxon_id": "min.unobtainium"},
        {**GOOD, "asset_id": "a4", "sha256": "d" * 64, "specimen_id": ""},
        {**GOOD, "asset_id": "a5", "sha256": "e" * 64, "license": ""},
        {**GOOD, "asset_id": "a6"},  # duplicate sha256 of GOOD
    ]
    problems = {e.asset_id: e.problem for e in validate_rows([GOOD, *bad])}
    assert set(problems) == {"a2", "a3", "a4", "a5", "a6"}


def test_manifest_header_rejects_label_columns():
    assert any("forbidden" in p for p in check_header([*GOOD, "ground_truth_id"]))
