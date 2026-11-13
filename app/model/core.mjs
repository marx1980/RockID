// Shared by the phone app (browser) and the build/eval job (Node). Must match
// services/identifier/knn.py (aggregate, decide); tests/test_js_parity.py checks this.

export const MODEL_ID = "onnx-community/dinov2-small";
export const DTYPE = "q8";

function l2(v) {
  let n = 0;
  for (let i = 0; i < v.length; i++) n += v[i] * v[i];
  n = Math.sqrt(n) || 1;
  for (let i = 0; i < v.length; i++) v[i] /= n;
  return v;
}

// DINOv2 last_hidden_state [1, T, D] -> L2(concat(L2(CLS), L2(mean of patch tokens))), length 2D.
export function vectorFromHidden(data, dims) {
  const T = dims[1], D = dims[2];
  const cls = new Float32Array(D), mean = new Float32Array(D);
  for (let d = 0; d < D; d++) cls[d] = data[d];
  for (let t = 1; t < T; t++) for (let d = 0; d < D; d++) mean[d] += data[t * D + d];
  for (let d = 0; d < D; d++) mean[d] /= Math.max(1, T - 1);
  l2(cls); l2(mean);
  const out = new Float32Array(2 * D);
  out.set(cls, 0); out.set(mean, D);
  return l2(out);
}

export async function embed(model, processor, image) {
  const inputs = await processor(image);
  const { last_hidden_state } = await model(inputs);
  return vectorFromHidden(last_hidden_state.data, last_hidden_state.dims);
}

export class ReferenceIndex {
  constructor(vectors, items, dim) {
    this.v = vectors; this.items = items; this.dim = dim;
  }
  search(q, k = 50, form = null) {
    const n = this.items.length, D = this.dim, sims = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      let s = 0;
      for (let d = 0; d < D; d++) s += this.v[i * D + d] * q[d];
      sims[i] = s;
    }
    let ids = Array.from(sims.keys());
    if (form !== null) ids = ids.filter(i => (this.items[i].f || "natural") === form);
    const order = ids.sort((a, b) => sims[b] - sims[a]).slice(0, k);
    return order.map(i => ({ item: this.items[i], similarity: sims[i] }));
  }
  count(form) { return this.items.filter(it => (it.f || "natural") === form).length; }
}

export function aggregate(neighbors, temperature = 0.05, maxSpecimensPerTaxon = 3, key = item => item.t) {
  const best = new Map();
  for (const n of neighbors) {
    const cur = best.get(n.item.s);
    if (!cur || n.similarity > cur.similarity) best.set(n.item.s, n);
  }
  const perTaxon = new Map();
  for (const n of [...best.values()].sort((a, b) => b.similarity - a.similarity)) {
    const b = perTaxon.get(key(n.item)) || [];
    if (b.length < maxSpecimensPerTaxon) b.push(n);
    perTaxon.set(key(n.item), b);
  }
  if (!perTaxon.size) return [];
  let top = -Infinity;
  for (const ns of perTaxon.values()) for (const n of ns) top = Math.max(top, n.similarity);
  const raw = [];
  let total = 0;
  for (const [t, ns] of perTaxon) {
    let v = 0;
    for (const n of ns) v += Math.exp((n.similarity - top) / temperature);
    raw.push([t, v, ns]); total += v;
  }
  return raw.map(([t, v, ns]) => ({
    taxon: t, p: v / total, bestSimilarity: ns[0].similarity, specimens: ns.map(n => n.item.s),
  })).sort((a, b) => b.p - a.p);
}

export const FORM_DEFAULTS = { min_form_p: 0.6, min_pool: 30 };

// Vote on the form (natural, tumbled, polished) from all references; when the vote is clear and the
// form has enough photos, rank taxa among references of that form only. Mirrors knn.identify.
export function identify(index, q, k = 50, formCfg = {}) {
  const cfg = { ...FORM_DEFAULTS, ...formCfg };
  const neighbors = index.search(q, k);
  const votes = aggregate(neighbors, 0.05, 3, item => item.f || "natural");
  const form = votes.length ? votes[0].taxon : "natural", formP = votes.length ? votes[0].p : 0;
  if (votes.length && formP >= cfg.min_form_p && index.count(form) >= cfg.min_pool)
    return { cands: aggregate(index.search(q, k, form)), form, formP, restricted: true };
  return { cands: aggregate(neighbors), form, formP, restricted: false };
}

export function decide(cands, cfg = {}) {
  const { ood_similarity = 0.35, accept_probability = 0.6, min_margin = 0.2, min_specimens = 2 } = cfg;
  if (!cands.length) return { status: "unknown", candidates: [] };
  const top = cands[0], three = cands.slice(0, 3);
  if (top.bestSimilarity < ood_similarity) return { status: "unknown", candidates: three };
  const margin = top.p - (cands.length > 1 ? cands[1].p : 0);
  if (top.p < accept_probability || margin < min_margin) return { status: "uncertain", candidates: three };
  if (top.specimens.length < min_specimens) return { status: "uncertain", candidates: three };
  return { status: "identified", candidates: three };
}
