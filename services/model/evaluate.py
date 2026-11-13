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
from services.identifier.knn import FORM_DEFAULTS, Neighbor, ReferenceIndex, ReferenceItem, aggregate, decide, identify

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
    return [ReferenceItem(it["id"], it["s"], it["t"], it.get("f", "natural")) for it in meta["items"]]


def _decide_rows(cands_list, truths, cfg) -> list[CaseResult]:
    rows = []
    for cands, truth in zip(cands_list, truths):
        d = decide(cands, **cfg)
        rows.append(CaseResult(truth=truth, ranked=[c.taxon_id for c in d.candidates],
                               abstained=d.status != "identified",
                               confidence=d.candidates[0].probability if d.candidates else None))
    return rows


def loso_candidates(vec: np.ndarray, meta: dict):
    """For each reference photo, vote on its form and rank taxa using only *other* specimens,
    exactly as the app does (form vote, then references of that form when the vote is clear)."""
    items = _items(meta)
    sims = vec @ vec.T
    forms = np.array([it.form for it in items])
    out, truths, best_correct, pred_forms = [], [], [], []
    for i, it in enumerate(items):
        keep = np.array([o.specimen_id != it.specimen_id for o in items])
        s_i = np.where(keep, sims[i], -np.inf)
        top = lambda mask: [j for j in np.argsort(-np.where(mask, s_i, -np.inf))[:50] if np.isfinite(s_i[j]) and mask[j]]
        neighbors = [Neighbor(items[j], float(s_i[j])) for j in top(np.ones(len(items), bool))]
        votes = aggregate(neighbors, key=lambda x: x.form)
        form, form_p = (votes[0].taxon_id, votes[0].probability) if votes else ("natural", 0.0)
        pool = forms == form
        if votes and form_p >= FORM_DEFAULTS["min_form_p"] and int((pool & keep).sum()) >= FORM_DEFAULTS["min_pool"]:
            neighbors = [Neighbor(items[j], float(s_i[j])) for j in top(pool)]
        cands = aggregate(neighbors)
        out.append(cands)
        truths.append(it.taxon_id)
        pred_forms.append(form)
        if cands and cands[0].taxon_id == it.taxon_id:
            best_correct.append(cands[0].best_similarity)
    return out, truths, best_correct, pred_forms


def calibrate(prefix, config_out, report_out=None) -> dict:
    vec, meta = load(prefix)
    cands, truths, best_correct, pred_forms = loso_candidates(vec, meta)
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
        "form": dict(FORM_DEFAULTS),
    }
    Path(config_out).write_text(json.dumps(config, indent=1))
    if report_out:
        Path(report_out).parent.mkdir(parents=True, exist_ok=True)
        true_forms = [it["f"] if "f" in it else "natural" for it in meta["items"]]
        by_form = {}
        for f in sorted(set(true_forms)):
            idx = [i for i, t in enumerate(true_forms) if t == f]
            sub = report(_decide_rows([cands[i] for i in idx], [truths[i] for i in idx], base))
            by_form[f] = {"photos": len(idx), "form_accuracy": sum(pred_forms[i] == f for i in idx) / len(idx),
                          "top1": sub["top1"], "top3": sub["top3"]}
        Path(report_out).write_text(json.dumps({"chosen": chosen, "loso_top1_top3": {"top1": loso_open["top1"], "top3": loso_open["top3"]},
                                                "by_form": by_form,
                                                "per_class_recall": loso_open["per_class_recall"], "sweep": sweep}, indent=1))
    return config


def score(ref_prefix, ch_prefix, challenge_csv, config_path, json_out, md_out) -> dict:
    rvec, rmeta = load(ref_prefix)
    cvec, cmeta = load(ch_prefix)
    config = json.loads(Path(config_path).read_text())
    cfg, form_cfg = config["decision"], config.get("form")
    index = ReferenceIndex(_items(rmeta), rvec)
    # Predictions are computed and frozen before any label is read.
    preds = {}
    for it, v in zip(cmeta["items"], cvec):
        cands, form, form_p, restricted = identify(index, v, 50, form_cfg)
        d = decide(cands, **cfg)
        preds[it["id"]] = {"status": d.status, "ranked": [c.taxon_id for c in d.candidates],
                           "p": [round(c.probability, 4) for c in d.candidates],
                           "form": form, "form_p": round(form_p, 4), "restricted": restricted}
    Path(json_out).parent.mkdir(parents=True, exist_ok=True)
    # baseline.json -> challenge_predictions.json; baseline_v2.json -> challenge_predictions_v2.json (earlier runs stay untouched)
    frozen = Path(json_out).with_name(Path(json_out).stem.replace("baseline", "challenge_predictions") + ".json")
    frozen.write_text(json.dumps(preds, indent=0, sort_keys=True))
    return rescore(frozen, challenge_csv, json_out, md_out, cfg, rmeta, len(cmeta.get("failed", [])))


def rescore(predictions_json, challenge_csv, json_out, md_out, cfg=None, rmeta=None, not_embedded=0) -> dict:
    """Score frozen predictions against the challenge labels (labels are read only here)."""
    preds = json.loads(Path(predictions_json).read_text())
    with Path(challenge_csv).open(newline="", encoding="utf-8") as fh:
        truth = {r["case_id"]: r["ground_truth_id"] for r in csv.DictReader(fh)}
    rows = [CaseResult(truth=truth[cid], ranked=p["ranked"], abstained=p["status"] != "identified",
                       confidence=p["p"][0] if p["p"] else None) for cid, p in sorted(preds.items())]
    r = report(rows)
    r["not_embedded"] = not_embedded
    r["status_counts"] = {s: sum(p["status"] == s for p in preds.values()) for s in ("identified", "uncertain", "unknown")}
    r["form_counts"] = {f: sum(p.get("form", "natural") == f for p in preds.values()) for f in ("natural", "tumbled", "polished")}
    if cfg is not None:
        r["decision"] = cfg
    Path(json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(json_out).write_text(json.dumps(r, indent=1))
    model = f"{rmeta['model']} ({rmeta['dtype']})" if rmeta else "see app/model/config.json"
    refs = len(rmeta["items"]) if rmeta else "?"
    lines = [
        f"# Baseline: {model}, specimen-balanced k-NN", "",
        f"Date {date.today().isoformat()} · reference photos {refs} · challenge cases {len(rows)} (not embedded: {not_embedded})", "",
        "Challenge photos come from photographers, specimens and source pages absent from the reference set.", "",
        "## Shortlist (ignores the app's confidence verdict)", "",
        "| metric | value |", "|---|---|",
        *[f"| {k} | {r[k]:.3f} |" for k in ("ranked_top1", "ranked_top3", "category_accuracy")],
        "", "## Committed answers (verdict = identified)", "",
        "| metric | value |", "|---|---|",
        *[f"| {k} | {r[k]:.3f} |" for k in ("coverage", "selective_accuracy", "confident_error_rate", "top1", "top3", "macro_f1", "ece")],
        "", f"Verdicts: {r['status_counts']}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.", "",
        "| class | recall@1 (committed) |", "|---|---|",
        *[f"| {k} | {v:.2f} |" for k, v in r["per_class_recall"].items()],
    ]
    Path(md_out).write_text("\n".join(lines) + "\n")
    return r


def score_forms(ref_prefix, set_prefix, set_csv, config_path, json_out, md_out) -> dict:
    """Held-out polished/tumbled photos: new specimens, labelled with taxon and form. Reports taxon
    accuracy and form detection per form. Same-institution photos are possible here, so read it as
    specimen-level hold-out only."""
    rvec, rmeta = load(ref_prefix)
    svec, smeta = load(set_prefix)
    config = json.loads(Path(config_path).read_text())
    index = ReferenceIndex(_items(rmeta), rvec)
    with Path(set_csv).open(newline="", encoding="utf-8") as fh:
        truth = {r["case_id"]: r for r in csv.DictReader(fh)}
    by: dict[str, list] = {}
    for it, v in zip(smeta["items"], svec):
        t = truth[it["id"]]
        cands, form, _p, restricted = identify(index, v, 50, config.get("form"))
        by.setdefault(t["form"], []).append((t["ground_truth_id"], [c.taxon_id for c in cands[:3]], form, restricted))
    out = {}
    for f, rows in sorted(by.items()):
        n = len(rows)
        out[f] = {"cases": n, "top1": sum(r[1][:1] == [r[0]] for r in rows) / n, "top3": sum(r[0] in r[1] for r in rows) / n,
                  "form_accuracy": sum(r[2] == f for r in rows) / n, "restricted": sum(r[3] for r in rows) / n}
    Path(json_out).write_text(json.dumps(out, indent=1))
    lines = ["# Polished and tumbled hold-out", "", "New specimens, not in the reference set; same institution and backdrop as some reference photos.", "",
             "| form | cases | form detected | top-1 | top-3 |", "|---|---|---|---|---|",
             *[f"| {f} | {v['cases']} | {v['form_accuracy']:.2f} | {v['top1']:.2f} | {v['top3']:.2f} |" for f, v in out.items()]]
    Path(md_out).write_text("\n".join(lines) + "\n")
    return out


OOD_FLOORS = [0.0, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]


def ood_sweep(ref_prefix, ood_prefix, ood_csv, config_path, json_out, md_out) -> dict:
    """Trade-off table for the abstention thresholds: for each setting, how often OOD photos are wrongly
    named (false accept) against how many reference photos still get an answer (coverage, leave-one-
    specimen-out). Run it on the calibration OOD cases only; the frozen OOD test is scored once with
    `score`, after a setting has been chosen."""
    rvec, rmeta = load(ref_prefix)
    ovec, ometa = load(ood_prefix)
    config = json.loads(Path(config_path).read_text())
    index = ReferenceIndex(_items(rmeta), rvec)
    with Path(ood_csv).open(newline="", encoding="utf-8") as fh:
        groups = {r["case_id"]: r.get("ood_group", "") for r in csv.DictReader(fh)}
    ood = [identify(index, v, 50, config.get("form"))[0] for v in ovec]
    ood_groups = [groups.get(it["id"], "") for it in ometa["items"]]
    loso, truths, _best, _forms = loso_candidates(rvec, rmeta)
    rows = []
    shipped = config["decision"]
    grid = [shipped] + [{"ood_similarity": f, "accept_probability": ap, "min_margin": mm, "min_specimens": ms}
                        for f in OOD_FLOORS for ap, mm, ms in itertools.product(*GRID.values())]
    for cfg in grid:
        far = [decide(c, **cfg).status == "identified" for c in ood]
        r = report(_decide_rows(loso, truths, cfg))
        by_group = {g: sum(f for f, og in zip(far, ood_groups) if og == g) / max(1, sum(og == g for og in ood_groups))
                    for g in sorted(set(ood_groups))}
        rows.append({**cfg, "ood_false_accept": sum(far) / len(far), "by_group": by_group,
                     "coverage": r["coverage"], "selective_accuracy": r["selective_accuracy"], "shipped": cfg is shipped})
    out = {"ood_cases": len(ood), "rows": rows}
    Path(json_out).write_text(json.dumps(out, indent=1))
    best = sorted((r for r in rows if r["selective_accuracy"] >= TARGET_SELECTIVE_ACCURACY), key=lambda r: (r["ood_false_accept"], -r["coverage"]))[:8]
    lines = ["# OOD false accepts vs coverage (calibration OOD cases)", "",
             f"{len(ood)} OOD calibration photos. Truth is UNKNOWN: any committed answer is a false accept.", "",
             "| setting | OOD false accept | coverage | selective accuracy |", "|---|---|---|---|"]
    for r in [rows[0]] + best:
        name = ("shipped " if r["shipped"] else "") + f"floor {r['ood_similarity']:.2f} · p {r['accept_probability']} · margin {r['min_margin']} · specimens {r['min_specimens']}"
        lines.append(f"| {name} | {r['ood_false_accept']:.2f} | {r['coverage']:.2f} | {r['selective_accuracy']:.2f} |")
    Path(md_out).write_text("\n".join(lines) + "\n")
    return {"ood_cases": len(ood), "shipped": rows[0], "best": best[:3]}


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    fn = {"calibrate": calibrate, "score": score, "rescore": rescore, "score_forms": score_forms, "ood_sweep": ood_sweep}[cmd]
    print(json.dumps(fn(*args), indent=1)[:2000])
