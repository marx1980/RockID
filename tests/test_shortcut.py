import csv
import json

import numpy as np

from services.model.shortcut import collection, shortcut_report


def _write(tmp_path, rows, vecs):
    vecs = np.asarray(vecs, dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs.tofile(tmp_path / "r.f32")
    items = [{"id": r["asset_id"], "s": r["specimen_id"], "t": r["taxon_id"]} for r in rows]
    (tmp_path / "r.json").write_text(json.dumps({"model": "m", "dtype": "q8", "dim": vecs.shape[1], "items": items}))
    with (tmp_path / "ref.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["asset_id", "specimen_id", "taxon_id", "source_name", "author"])
        w.writeheader()
        w.writerows(rows)


def test_collection_uses_photographer_for_commons():
    assert collection({"source_name": "Wikimedia Commons", "author": "Ann"}) == "commons:ann"
    assert collection({"source_name": "NHM", "author": "x"}) == "NHM"


def test_backdrop_driven_embeddings_show_a_collection_shortcut(tmp_path):
    # Vectors encode the collection (backdrop) strongly and the taxon weakly.
    rng = np.random.default_rng(1)
    rows, vecs = [], []
    backdrop = {"A": np.eye(8)[0], "B": np.eye(8)[1]}
    taxon = {"t1": np.eye(8)[2], "t2": np.eye(8)[3]}
    for coll in "AB":
        for t in ("t1", "t2"):
            for k in range(6):
                rows.append({"asset_id": f"{coll}{t}{k}", "specimen_id": f"{coll}{t}{k}", "taxon_id": t, "source_name": coll, "author": ""})
                vecs.append(3 * backdrop[coll] + taxon[t] + 0.05 * rng.normal(size=8))
    _write(tmp_path, rows, vecs)
    r = shortcut_report(tmp_path / "r", tmp_path / "ref.csv")
    assert r["photos"] == 24
    assert r["nn_same_collection"] > r["nn_same_collection_chance"]
    assert r["specimen_out_top1"] == 1.0
    assert r["collection_out_top1"] <= r["specimen_out_top1"]
