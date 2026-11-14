"""Pre-registered scoring for challenge set C (stones with 2-5 photos). Written and merged before C exists, so
the primary rule and metric cannot be picked after seeing results. Rules: docs/CHALLENGE_C.md, section
"Pre-registration". Inputs are per-photo probability rows over a fixed class list; nothing here reads images.

Primary: rule mean_prob over the first PRIMARY_K views of each stone, stone-level top-1 on live-class stones,
compared with the single-photo baseline on the same views; gain with a paired bootstrap 95% interval.
"""
import numpy as np

FLOOR = 1e-4
RULES = ("mean_prob", "mean_logprob", "max_conf", "vote")
PRIMARY_RULE, PRIMARY_K = "mean_prob", 3
BOOTSTRAP, SEED = 10_000, 20261114
TAU_P = tuple(round(0.30 + 0.05 * i, 2) for i in range(13))  # 0.30 .. 0.90
TAU_S = tuple(round(0.50 + 0.02 * i, 2) for i in range(21))  # 0.50 .. 0.90
MAX_OOD_NAMED = 0.05


def combine(P: np.ndarray, rule: str = PRIMARY_RULE) -> np.ndarray:
    """P: (views, classes) probability rows -> one probability row."""
    P = np.asarray(P, dtype=float)
    if rule == "mean_prob":
        return P.mean(0)
    if rule == "mean_logprob":
        q = np.exp(np.log(np.maximum(P, FLOOR)).mean(0))
        return q / q.sum()
    if rule == "max_conf":
        return P[int(np.argmax(P.max(1)))]
    if rule == "vote":  # most top-1 votes; ties broken by mean probability (always < 1 vote)
        s = np.bincount(P.argmax(1), minlength=P.shape[1]) + P.mean(0)
        return s / s.sum()
    raise ValueError(rule)


def _rank(p: np.ndarray, j: int) -> int:
    return int((p > p[j]).sum())  # 0 = top-1; ties count in the truth's favour


def stones(cases: list[dict], probs: dict[str, np.ndarray], classes: list[str], rule: str = PRIMARY_RULE,
           k: int | None = PRIMARY_K, scope: str | None = "live") -> list[dict]:
    """cases: challenge_c.csv rows. Returns one result per stone whose truth is in `classes` (and in `scope`)."""
    col = {c: i for i, c in enumerate(classes)}
    by: dict[str, list[dict]] = {}
    for r in cases:
        if (scope is None or r.get("scope") == scope) and r["ground_truth_id"] in col and r["case_id"] in probs:
            by.setdefault(r["stone_id"], []).append(r)
    out = []
    for sid, views in sorted(by.items()):
        views = sorted(views, key=lambda r: int(r["view"]))[:k]
        if len(views) < 2:
            continue
        j = col[views[0]["ground_truth_id"]]
        P = np.stack([probs[r["case_id"]] for r in views])
        single = [_rank(p, j) for p in P]
        multi = _rank(combine(P, rule), j)
        out.append({"stone_id": sid, "truth": views[0]["ground_truth_id"], "views": len(views),
                    "single_top1": float(np.mean([r == 0 for r in single])), "single_top3": float(np.mean([r < 3 for r in single])),
                    "multi_top1": float(multi == 0), "multi_top3": float(multi < 3)})
    return out


def summary(results: list[dict], seed: int = SEED, n_boot: int = BOOTSTRAP) -> dict:
    """Stone-weighted means and the paired gain multi - single with a bootstrap 95% interval over stones."""
    if not results:
        return {"stones": 0}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(results), size=(n_boot, len(results)))
    out = {"stones": len(results)}
    for m in ("top1", "top3"):
        s = np.array([r[f"single_{m}"] for r in results])
        g = np.array([r[f"multi_{m}"] for r in results])
        boot = (g[idx] - s[idx]).mean(1)
        out[m] = {"single": round(float(s.mean()), 4), "multi": round(float(g.mean()), 4),
                  "gain": round(float((g - s).mean()), 4),
                  "ci95": [round(float(np.percentile(boot, 2.5)), 4), round(float(np.percentile(boot, 97.5)), 4)]}
    out["primary_supported"] = out["top1"]["ci95"][0] > 0
    return out


def verdict(p: np.ndarray, sim: float, tau_p: float, tau_s: float) -> bool:
    """Identified iff the ranking is confident (head probability) and the evidence is close (nearest reference
    photo of the top class)."""
    return float(np.max(p)) >= tau_p and sim >= tau_s


def choose_thresholds(ood_p, ood_sim, cv_p, cv_sim, cv_correct, max_ood_named: float = MAX_OOD_NAMED):
    """Grid search, pre-registered: among (tau_p, tau_s) whose OOD-calibration named rate is <= max_ood_named,
    maximise correct answers on reference cross-validation; ties -> higher tau_s, then higher tau_p.
    Never called with A, B, C or the OOD test set."""
    best = None
    for tp in TAU_P:
        for ts in TAU_S:
            named = np.mean([verdict(p, s, tp, ts) for p, s in zip(ood_p, ood_sim)])
            if named > max_ood_named:
                continue
            good = sum(verdict(p, s, tp, ts) and c for p, s, c in zip(cv_p, cv_sim, cv_correct))
            key = (good, ts, tp)
            if best is None or key > best[0]:
                best = (key, {"tau_p": tp, "tau_s": ts, "ood_named": round(float(named), 4), "cv_correct": int(good)})
    return best[1] if best else None
