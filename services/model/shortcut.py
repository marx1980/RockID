"""Does the collection a photo comes from (backdrop, lighting, scale bar) do the identifying?

  python -m services.model.shortcut <embeddings prefix> <reference.csv> <json out> [md out]

For reference photos, k-NN over other specimens (as in calibration), reported three ways:
  specimen_out   other specimens may come from the same collection (what calibration uses)
  collection_out every photo from the query's collection is removed too
  random_out     control: as many photos removed as collection_out, at random from other collections
  nn_same        how often the nearest other specimen's collection names the query's collection
Taxa with a single collection are left out of the comparison (removing the collection removes the
taxon). A collection is the source, except Wikimedia Commons, where it is the photographer.
Run on embeddings with the centre masked (compare-model mask=0.6) for a backdrop-only reading.
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from services.identifier.knn import Neighbor, aggregate
from services.model.evaluate import _items, load


def collection(row: dict) -> str:
    if row["source_name"] == "Wikimedia Commons":
        return "commons:" + (row.get("author") or "").strip().lower()
    return row["source_name"]


def _top1(items, sims_i, mask) -> str | None:
    s = np.where(mask, sims_i, -np.inf)
    idx = [j for j in np.argsort(-s)[:50] if np.isfinite(s[j])]
    cands = aggregate([Neighbor(items[j], float(s[j])) for j in idx])
    return cands[0].taxon_id if cands else None


def shortcut_report(prefix, reference_csv) -> dict:
    vec, meta = load(prefix)
    items = _items(meta)
    with Path(reference_csv).open(newline="", encoding="utf-8") as fh:
        coll_of = {r["asset_id"]: collection(r) for r in csv.DictReader(fh)}
    colls = np.array([coll_of.get(it.asset_id, "?") for it in items])
    specs = np.array([it.specimen_id for it in items])
    taxa = np.array([it.taxon_id for it in items])
    natural = np.array([it.form == "natural" for it in items])
    n_coll = defaultdict(set)
    for t, c in zip(taxa, colls):
        n_coll[t].add(c)
    sims = vec @ vec.T
    rng = np.random.default_rng(0)
    rows = []
    for i in range(len(items)):
        if not natural[i] or len(n_coll[taxa[i]]) < 2:
            continue
        other_spec = (specs != specs[i]) & natural
        other_coll = other_spec & (colls != colls[i])
        if not (other_coll & (taxa == taxa[i])).any():
            continue
        # control: drop as many photos as collection_out does, but at random from other collections
        drop_n = int((other_spec & (colls == colls[i])).sum())
        pool = np.flatnonzero(other_coll)
        ctrl = other_spec.copy()
        ctrl[rng.choice(pool, size=min(drop_n, max(0, len(pool) - 1)), replace=False)] = False
        s = np.where(other_spec, sims[i], -np.inf)
        nn = int(np.argmax(s))
        rows.append({
            "taxon": taxa[i], "collection": colls[i],
            "specimen_out": _top1(items, sims[i], other_spec) == taxa[i],
            "collection_out": _top1(items, sims[i], other_coll) == taxa[i],
            "random_out": _top1(items, sims[i], ctrl) == taxa[i],
            "nn_same_collection": colls[nn] == colls[i],
            "chance_same_collection": float((colls[other_spec] == colls[i]).mean()),
        })
    acc = lambda key, rs: round(sum(r[key] for r in rs) / max(1, len(rs)), 3)
    by_coll = defaultdict(list)
    for r in rows:
        by_coll[r["collection"] if not r["collection"].startswith("commons:") else "Wikimedia Commons (any photographer)"].append(r)
    return {
        "model": meta.get("model"), "mask": meta.get("mask", 0), "photos": len(rows),
        "specimen_out_top1": acc("specimen_out", rows),
        "collection_out_top1": acc("collection_out", rows),
        "random_out_top1": acc("random_out", rows),
        "nn_same_collection": acc("nn_same_collection", rows),
        "nn_same_collection_chance": round(float(np.mean([r["chance_same_collection"] for r in rows])) if rows else 0.0, 3),
        "by_collection": {c: {"photos": len(rs), "specimen_out_top1": acc("specimen_out", rs),
                              "collection_out_top1": acc("collection_out", rs), "nn_same_collection": acc("nn_same_collection", rs)}
                          for c, rs in sorted(by_coll.items(), key=lambda kv: -len(kv[1]))},
        "taxa_left_out": sorted(t for t, c in n_coll.items() if len(c) < 2),
    }


def challenge_by_collection(predictions_json, challenge_csv, reference_csv) -> dict:
    """Frozen challenge predictions split by whether the case's collection also supplies reference photos."""
    preds = json.loads(Path(predictions_json).read_text())
    with Path(reference_csv).open(newline="", encoding="utf-8") as fh:
        seen = {collection(r) for r in csv.DictReader(fh)}
    groups = defaultdict(list)
    with Path(challenge_csv).open(newline="", encoding="utf-8") as fh:
        for c in csv.DictReader(fh):
            p = preds.get(c["case_id"])
            if not p:
                continue
            hit = (p["ranked"][:1] == [c["ground_truth_id"]], c["ground_truth_id"] in p["ranked"][:3])
            groups["collection in reference set" if collection(c) in seen else "new collection"].append(hit)
            groups[c["source_name"]].append(hit)
    return {k: {"cases": len(v), "top1": round(sum(a for a, _ in v) / len(v), 3), "top3": round(sum(b for _, b in v) / len(v), 3)}
            for k, v in groups.items()}


def to_md(r: dict) -> str:
    lines = [f"# Collection shortcut check ({r['model']}, centre mask {r['mask']})", "",
             f"{r['photos']} natural reference photos of taxa found in two or more collections.", "",
             "| reading | value |", "|---|---|",
             f"| top-1, other specimens | {r['specimen_out_top1']:.3f} |",
             f"| top-1, other collections only | {r['collection_out_top1']:.3f} |",
             f"| top-1, same number of photos removed at random | {r['random_out_top1']:.3f} |",
             f"| nearest specimen from same collection | {r['nn_same_collection']:.3f} (chance {r['nn_same_collection_chance']:.3f}) |",
             "", "| collection | photos | top-1 other specimens | top-1 other collections | nearest same collection |", "|---|---|---|---|---|",
             *[f"| {c} | {v['photos']} | {v['specimen_out_top1']:.2f} | {v['collection_out_top1']:.2f} | {v['nn_same_collection']:.2f} |"
               for c, v in r["by_collection"].items()],
             "", f"Left out (one collection): {', '.join(r['taxa_left_out']) or 'none'}"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if sys.argv[1] == "challenge":
        print(json.dumps(challenge_by_collection(*sys.argv[2:5]), indent=1))
        sys.exit()
    prefix, ref_csv, json_out, *md = sys.argv[1:]
    r = shortcut_report(prefix, ref_csv)
    Path(json_out).write_text(json.dumps(r, indent=1))
    if md:
        Path(md[0]).write_text(to_md(r))
    print(to_md(r))
