import csv

from services.ingestion.private_mineralimage5k import split


def test_ood_species_never_on_both_sides_and_labels_have_no_paths(tmp_path):
    rows = [{"asset_id": f"a{i}", "taxon_id": f"ood.c{i % 6}" if i % 3 else "min.quartz", "dataset_class": f"c{i % 6}",
             "specimen_id": f"a{i}", "form": "natural", "source_name": "S", "license": "L", "media_url": f"/tmp/{i}.jpg"} for i in range(36)]
    with (tmp_path / "manifest.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    split(str(tmp_path))
    cal = list(csv.DictReader((tmp_path / "ood_cal.csv").open()))
    test = list(csv.DictReader((tmp_path / "ood_test.csv").open()))
    assert cal and test and not ({r["dataset_class"] for r in cal} & {r["dataset_class"] for r in test})
    assert {r["ground_truth_id"] for r in cal + test} == {"UNKNOWN"}
    for name in ("ref_labels.csv", "ood_cal.csv", "ood_test.csv"):
        assert "media_url" not in (tmp_path / name).read_text().splitlines()[0]
