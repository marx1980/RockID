import base64
import csv
import io
import json

from PIL import Image

from services.curation.own_photos import ingest


def _photo(color):
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def test_labelled_photos_split_into_reference_and_ood(tmp_path):
    ref = tmp_path / "data_manifests/reference"
    ref.mkdir(parents=True)
    cols = ["asset_id", "taxon_id", "specimen_id", "source_name", "source_url", "author", "license", "retrieval_date", "usage_decision", "sha256", "phash", "media_url", "form"]
    with (ref / "reference.csv").open("w", newline="") as fh:
        csv.writer(fh).writerow(cols)
    export = tmp_path / "e.json"
    export.write_text(json.dumps({"app": "rockid-labels", "v": 1, "items": [
        {"id": "a1", "at": "2026-11-14T10:00:00Z", "truth": "min.quartz", "other": "", "form": "natural", "predicted": {"status": "uncertain", "top": [{"taxon": "min.calcite", "p": 0.4}]}, "photo": _photo("red")},
        {"id": "a2", "at": "2026-11-14T10:05:00Z", "truth": "min.quartz", "other": "", "form": "polished", "predicted": {"status": "identified", "top": []}, "photo": _photo("blue")},
        {"id": "b1", "at": "2026-11-14T11:00:00Z", "truth": "other", "other": "sulfur", "predicted": {"status": "identified", "top": [{"taxon": "min.pyrite", "p": 0.6}]}, "photo": _photo("green")},
    ]}))
    assert ingest([str(export)], tmp_path) == {"reference": 2, "ood": 1, "skipped": 0}
    rows = list(csv.DictReader((ref / "reference.csv").open()))
    assert {r["specimen_id"] for r in rows} == {"own:min.quartz:2026-11-14"} and rows[1]["form"] == "polished"
    assert rows[0]["license"] == "Own work" and (tmp_path / rows[0]["media_url"]).exists()
    ood = list(csv.DictReader((tmp_path / "data_manifests/own_photos/ood.csv").open()))
    assert ood[0]["other_name"] == "sulfur" and ood[0]["predicted_top1"] == "min.pyrite"
    assert ingest([str(export)], tmp_path)["skipped"] == 3  # re-importing the same export changes nothing
