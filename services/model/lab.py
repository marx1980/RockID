"""Offline lab on stored vectors: which classifier design survives many classes and single-source classes.
Run: python3 -I lab.py /home/claude/o2/lab"""
import json, sys, collections
import numpy as np
from sklearn.linear_model import LogisticRegression

D = sys.argv[1]


def load(name, src):
    m = json.load(open(f"{D}/{name}.json"))
    v = np.fromfile(f"{D}/{name}.f32", dtype=np.float32).reshape(len(m["items"]), m["dim"])
    v = v / np.linalg.norm(v, axis=1, keepdims=True)
    t = np.array([i["t"] for i in m["items"]])
    s = np.array([i["s"] for i in m["items"]])
    c = np.array([src or i["id"].split(":")[0] for i in m["items"]])
    return v, t, s, c


def cat(*sets):
    return tuple(np.concatenate([x[i] for x in sets]) for i in range(4))


def sub(S, mask):
    return tuple(x[mask] for x in S)


pub = load("reference", None)
ref11 = load("mi5k_ref", "mi5k")
new76 = load("mi5k_all", "mi5k")
kg = cat(*[load(f"kg_v{i}", "kg") for i in range(1, 6)])


def knn(R, Q, k=50, cap=3, T=0.05, exclude_same_specimen=False):
    """Current app rule: top-k pool, best photo per specimen, cap specimens per taxon, softmax."""
    rv, rt, rs, _ = R
    out = []
    sims_all = Q[0] @ rv.T
    for qi in range(len(Q[0])):
        sims = sims_all[qi].copy()
        if exclude_same_specimen:
            sims[rs == Q[2][qi]] = -9
        order = np.argsort(-sims) if k is None else np.argsort(-sims)[:k]
        seen, per = set(), collections.defaultdict(list)
        for i in order:
            if sims[i] < -1 or rs[i] in seen:
                continue
            seen.add(rs[i])
            if len(per[rt[i]]) < cap:
                per[rt[i]].append(sims[i])
        top = max(max(v) for v in per.values())
        sc = {t: sum(np.exp((x - top) / T) for x in v) for t, v in per.items()}
        out.append([t for t, _ in sorted(sc.items(), key=lambda x: -x[1])[:3]])
    return out


def linear(R, Q, C=10.0):
    clf = LogisticRegression(C=C, max_iter=300, class_weight="balanced")
    clf.fit(R[0], R[1])
    p = clf.predict_proba(Q[0])
    return [[clf.classes_[j] for j in np.argsort(-row)[:3]] for row in p]


def centroid(R, Q):
    cls = sorted(set(R[1]))
    M = np.stack([R[0][R[1] == c].mean(0) for c in cls])
    M /= np.linalg.norm(M, axis=1, keepdims=True)
    return [[cls[j] for j in np.argsort(-row)[:3]] for row in Q[0] @ M.T]


def deshortcut(R, Qs, d=8):
    """Remove directions that separate collections (class-balanced collection means), from reference and queries."""
    rv, rt, rs, rc = R
    mu = rv.mean(0)
    means = np.stack([rv[rc == c].mean(0) - mu for c in sorted(set(rc))])
    u, s, vt = np.linalg.svd(means, full_matrices=False)
    B = vt[: min(d, len(means) - 1)]

    def proj(v):
        w = v - (v @ B.T) @ B
        return w / np.linalg.norm(w, axis=1, keepdims=True)

    return (proj(rv), rt, rs, rc), [(proj(q[0]),) + q[1:] for q in Qs]


def acc(pred, truth):
    n = len(truth)
    return (round(sum(p[0] == t for p, t in zip(pred, truth)) / n, 3), round(sum(t in p for p, t in zip(pred, truth)) / n, 3))


def report(title, R, Q, loso=False):
    row = {"kNN now (k=50)": acc(knn(R, Q, exclude_same_specimen=loso), Q[1]),
           "kNN whole set": acc(knn(R, Q, k=None, exclude_same_specimen=loso), Q[1])}
    if not loso:
        row["centroid"] = acc(centroid(R, Q), Q[1])
        row["linear head"] = acc(linear(R, Q), Q[1])
        R2, (Q2,) = deshortcut(R, [Q])
        row["kNN now, de-shortcut"] = acc(knn(R2, Q2), Q2[1])
        row["linear, de-shortcut"] = acc(linear(R2, Q2), Q2[1])
    print(f"\n{title}  (ref {len(R[0])} photos, {len(set(R[1]))} classes; queries {len(Q[0])})")
    for k, v in row.items():
        print(f"  {k:24} top-1 {v[0]:.3f}  top-3 {v[1]:.3f}")
    return row


old5 = np.isin(kg[1], list(set(pub[1])))
kg_old, kg_new = sub(kg, old5), sub(kg, ~old5)

print("=== A. Web photos of 5 existing classes (Kaggle, unseen source) as queries")
report("A1 reference = live 21 classes", pub, kg_old)
report("A2 + 76 museum classes", cat(pub, new76), kg_old)
report("A3 + 76 museum classes + museum photos of old classes", cat(pub, ref11, new76), kg_old)

print("\n=== B. Museum (Fersman) photos of 11 existing classes as queries: worst case for the shortcut")
report("B1 reference = live 21 classes + Kaggle", cat(pub, kg), ref11)
report("B2 + 76 museum classes", cat(pub, kg, new76), ref11)

print("\n=== C. Simulated single-source class: 11 classes known ONLY from museum photos, queried with photos from elsewhere")
m11 = np.isin(pub[1], list(set(ref11[1])))
q_c = sub(pub, m11)
report("C1 multi-source reference (leave-one-specimen-out)", pub, q_c, loso=True)
report("C2 those 11 classes museum-only, other 10 classes multi-source", cat(sub(pub, ~m11), ref11), q_c)
report("C3 same, plus 76 museum classes", cat(sub(pub, ~m11), ref11, new76), q_c)

print("\n=== D. Live reference photos, leave-one-specimen-out: how many are pulled away by new classes")
report("D1 21 classes", pub, pub, loso=True)
report("D2 + 76 museum classes", cat(pub, new76), pub, loso=True)
