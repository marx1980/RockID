import csv
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from services.identifier.knn import Neighbor, ReferenceItem, aggregate, decide
from services.model.evaluate import calibrate, score

ROOT = Path(__file__).resolve().parents[1]


def _write(prefix: Path, vec: np.ndarray, items: list[dict]):
    vec.astype(np.float32).tofile(f"{prefix}.f32")
    Path(f"{prefix}.json").write_text(json.dumps({"model": "test", "dtype": "fp32", "dim": vec.shape[1], "items": items, "failed": []}))


def _clustered(rng, n_taxa=4, specimens=4, photos=3, dim=16, noise=0.15):
    centers = rng.normal(size=(n_taxa, dim))
    vec, items = [], []
    for t in range(n_taxa):
        for s in range(specimens):
            spec = centers[t] + rng.normal(scale=noise, size=dim)
            for p in range(photos):
                v = spec + rng.normal(scale=noise / 3, size=dim)
                vec.append(v / np.linalg.norm(v))
                items.append({"id": f"a{t}-{s}-{p}", "s": f"s{t}-{s}", "t": f"t{t}"})
    return np.array(vec), items, centers


def test_calibrate_and_score_end_to_end(tmp_path):
    rng = np.random.default_rng(0)
    vec, items, centers = _clustered(rng)
    _write(tmp_path / "ref", vec, items)
    cfg = calibrate(tmp_path / "ref", tmp_path / "config.json", tmp_path / "loso.json")
    assert cfg["met_target"] and 0 < cfg["decision"]["ood_similarity"] < 1

    ch, truth = [], []
    for t in range(4):
        for k in range(3):
            v = centers[t] + rng.normal(scale=0.15, size=16)
            ch.append(v / np.linalg.norm(v)); truth.append((f"c{t}{k}", f"t{t}"))
    _write(tmp_path / "ch", np.array(ch), [{"id": cid} for cid, _ in truth])
    with (tmp_path / "challenge.csv").open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["case_id", "ground_truth_id"]); w.writerows(truth)
    r = score(tmp_path / "ref", tmp_path / "ch", tmp_path / "challenge.csv", tmp_path / "config.json",
              tmp_path / "out/baseline.json", tmp_path / "out/BASELINE.md")
    assert r["top1"] > 0.9 and r["cases"] == 12
    assert (tmp_path / "out/challenge_predictions.json").exists()
    assert "| top1 |" in (tmp_path / "out/BASELINE.md").read_text()


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_and_python_decisions_match(tmp_path):
    rng = np.random.default_rng(1)
    vec, items, _ = _clustered(rng, n_taxa=5, specimens=3, photos=4, noise=0.3)
    queries = rng.normal(size=(20, vec.shape[1]))
    queries /= np.linalg.norm(queries, axis=1, keepdims=True)
    queries[:10] = vec[rng.integers(0, len(vec), 10)] + rng.normal(scale=0.05, size=(10, vec.shape[1]))
    cfg = {"ood_similarity": 0.3, "accept_probability": 0.5, "min_margin": 0.1, "min_specimens": 2}
    expected = []
    ref_items = [ReferenceItem(it["id"], it["s"], it["t"]) for it in items]
    for q in queries:
        sims = vec @ q
        order = np.argsort(-sims)[:50]
        d = decide(aggregate([Neighbor(ref_items[i], float(sims[i])) for i in order]), **cfg)
        expected.append({"status": d.status, "ranked": [c.taxon_id for c in d.candidates],
                         "p": [round(c.probability, 5) for c in d.candidates]})
    fixture = {"dim": vec.shape[1], "vectors": vec.astype(np.float32).ravel().tolist(), "items": items,
               "queries": queries.astype(np.float32).tolist(), "cfg": cfg}
    (tmp_path / "f.json").write_text(json.dumps(fixture))
    script = f"""
import {{ ReferenceIndex, aggregate, decide }} from "{(ROOT / 'app/model/core.mjs').as_uri()}";
import fs from "node:fs";
const f = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const idx = new ReferenceIndex(Float32Array.from(f.vectors), f.items, f.dim);
const out = f.queries.map(q => {{ const d = decide(aggregate(idx.search(Float32Array.from(q), 50)), f.cfg);
  return {{ status: d.status, ranked: d.candidates.map(c => c.taxon), p: d.candidates.map(c => Math.round(c.p * 1e5) / 1e5) }}; }});
console.log(JSON.stringify(out));
"""
    (tmp_path / "run.mjs").write_text(script)
    got = json.loads(subprocess.run(["node", str(tmp_path / "run.mjs"), str(tmp_path / "f.json")],
                                    capture_output=True, text=True, check=True).stdout)
    for e, g in zip(expected, got):
        assert e["status"] == g["status"] and e["ranked"] == g["ranked"]
        assert np.allclose(e["p"], g["p"], atol=2e-4)


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_vector_from_hidden(tmp_path):
    (tmp_path / "v.mjs").write_text(f"""
import {{ vectorFromHidden }} from "{(ROOT / 'app/model/core.mjs').as_uri()}";
const D = 2, T = 3, data = Float32Array.from([3, 4,  1, 0,  0, 1]);
console.log(JSON.stringify(Array.from(vectorFromHidden(data, [1, T, D]))));
""")
    v = json.loads(subprocess.run(["node", str(tmp_path / "v.mjs")], capture_output=True, text=True, check=True).stdout)
    cls = np.array([0.6, 0.8]); mean = np.array([0.5, 0.5]) / np.linalg.norm([0.5, 0.5])
    expect = np.concatenate([cls, mean]); expect /= np.linalg.norm(expect)
    assert np.allclose(v, expect, atol=1e-6)
