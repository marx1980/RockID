"""Calibrate thresholds on the reference set (leave-one-specimen-out) and score the challenge set.

  python -m services.model.evaluate calibrate app/model/reference app/model/config.json results/loso.json
  python -m services.model.evaluate score app/model/reference /tmp/challenge vault/challenge.csv \
      app/model/config.json results/baseline.json results/BASELINE.md

Thresholds are chosen on reference data only; the challenge set is scored once with them.
"""
import csv
import itertools
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

from services.evaluator.metrics import CaseResult, report
from services.identifier.knn import Neighbor, ReferenceIndex, ReferenceItem, aggregate, decide

GRID = {
    "accept_probability": [0.4, 0.5, 0.6, 0.7, 0.8],
    "min_margin": [0.0, 0.1, 0.2, 0.3],
    "min_specimens": [1, 2],
}
TARGET_SELECTIVE_ACCURACY = 0.8


def load(prefix: str | Path) -> tuple[np.ndarray, dict]:
    meta = json.loads(Path(f"{prefix}.json").read_text())
    vec = np.fromfile(f"{prefix}.f32", dtype=np.float32).reshape(len(meta["items"]), meta["dim"])
    return vec, meta


def _items(meta) -> list[ReferenceItem]:
    return [ReferenceItem(it["id"], it["s"], it["t"]) for it in meta["items"]]


def _decide_rows(cands_list, truths, cfg) -> list[CaseResult]:
    rows = []
    for cands, truth in zip(cands_list, truths):
        d = decide(cands, **cfg)
        rows.append(CaseResult(truth=truth, ranked=[c.taxon_id for c in d.candidates],
                               abstained=d.status != "identified",
                               confidence=d.candidates[0].probability if d.candidates else None))
    return rows


def loso_candidates(vec: np.ndarray, meta: dict):
    """For each reference photo, rank taxa using only *other* specimens."""
    items = _items(meta)
    sims = vec @ vec.T
    out, truths, best_correct = [], [], []
    for i, it in enumerate(items):
        keep = [j for j, o in enumerate(items) if o.specimen_id != it.specimen_id]
        order = sorted(keep, key=lambda j: -sims[i, j])[:50]
        cands = aggregate([Neighbor(items[j], float(sims[i, j])) for j in order])
        out.append(cands)
        truths.append(it.taxon_id)
        if cands and cands[0].taxon_id == it.taxon_id:
            best_correct.append(cands[0].best_similarity)
    return out, truths, best_correct


def calibrate(prefix, config_out, report_out=None) -> dict:
    vec, meta = load(prefix)
    cands, truths, best_correct = loso_candidates(vec, meta)
    # Out-of-distribution floor: below what 95% of correct matches reach.
    ood = float(np.percentile(best_correct, 5)) if best_correct else 0.35
    sweep, chosen = [], None
    for ap, mm, ms in itertools.product(*GRID.values()):
        cfg = {"ood_similarity": ood, "accept_probability": ap, "min_margin": mm, "min_specimens": ms}
        r = report(_decide_rows(cands, truths, cfg))
        sweep.append({**cfg, "coverage": r["coverage"], "selective_accuracy": r["selective_accuracy"], "top1": r["top1"]})
    ok = [s for s in sweep if s["selective_accuracy"] >= TARGET_SELECTIVE_ACCURACY]
    chosen = max(ok or sweep, key=lambda s: (s["coverage"], s["selective_accuracy"]) if ok else (s["selective_accuracy"], s["coverage"]))
    cfg = {k: chosen[k] for k in ("ood_similarity", "accept_probability", "min_margin", "min_specimens")}
    base = {"ood_similarity": ood, "accept_probability": 0.0, "min_margin": 0.0, "min_specimens": 1}
    loso_open = report(_decide_rows(cands, truths, base))
    config = {
        "model": meta["model"], "dtype": meta["dtype"], "dim": meta["dim"], "decision": cfg,
        "calibrated_on": "reference leave-one-specimen-out", "target_selective_accuracy": TARGET_SELECTIVE_ACCURACY,
        "met_target": bool(ok), "reference_photos": len(meta["items"]), "date": date.today().isoformat(),
    }
    Path(config_out).write_text(json.dumps(config, indent=1))
    if report_out:
        Path(report_out).parent.mkdir(parents=True, exist_ok=True)
        Path(report_out).write_text(json.dumps({"chosen": chosen, "loso_top1_top3": {"top1": loso_open["top1"], "top3": loso_open["top3"]},
                                                "per_class_recall": loso_open["per_class_recall"], "sweep": sweep}, indent=1))
    return config


def score(ref_prefix, ch_prefix, challenge_csv, config_path, json_out, md_out) -> dict:
    rvec, rmeta = load(ref_prefix)
    cvec, cmeta = load(ch_prefix)
    cfg = json.loads(Path(config_path).read_text())["decision"]
    index = ReferenceIndex(_items(rmeta), rvec)
    # Predictions are computed and frozen before any label is read.
    preds = {}
    for it, v in zip(cmeta["items"], cvec):
        d = decide(aggregate(index.search(v, k=50)), **cfg)
        preds[it["id"]] = {"status": d.status, "ranked": [c.taxon_id for c in d.candidates],
                           "p": [round(c.probability, 4) for c in d.candidates]}
    Path(json_out).parent.mkdir(parents=True, exist_ok=True)
    frozen = Path(json_out).with_name("challenge_predictions.json")
    frozen.write_text(json.dumps(preds, indent=0, sort_keys=True))
    with Path(challenge_csv).open(newline="", encoding="utf-8") as fh:
        truth = {r["case_id"]: r["ground_truth_id"] for r in csv.DictReader(fh)}
    rows = [CaseResult(truth=truth[cid], ranked=p["ranked"], abstained=p["status"] != "identified",
                       confidence=p["p"][0] if p["p"] else None) for cid, p in sorted(preds.items())]
    r = report(rows)
    r["not_embedded"] = len(cmeta.get("failed", []))
    r["decision"] = cfg
    Path(json_out).write_text(json.dumps(r, indent=1))
    lines = [
        f"# Baseline: {rmeta['model']} ({rmeta['dtype']}), specimen-balanced k-NN", "",
        f"Date {date.today().isoformat()} · reference photos {len(rmeta['items'])} · challenge cases {len(rows)}"
        f" (not embedded: {r['not_embedded']})", "",
        "| metric | value |", "|---|---|",
        *[f"| {k} | {r[k]:.3f} |" for k in ("top1", "top3", "macro_f1", "coverage", "selective_accuracy",
                                           "confident_error_rate", "ece")],
        "", "Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.", "",
        "| class | recall@1 |", "|---|---|",
        *[f"| {k} | {v:.2f} |" for k, v in r["per_class_recall"].items()],
    ]
    Path(md_out).write_text("\n".join(lines) + "\n")
    return r


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    print(json.dumps(calibrate(*args) if cmd == "calibrate" else score(*args), indent=1)[:2000])
