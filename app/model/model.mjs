// In-browser identifier: DINOv2-small (transformers.js, ONNX) + specimen-balanced k-NN over the
// reference vectors built by the build-model workflow. Weights are fetched on first use and cached.
import { MODEL_ID, DTYPE, embed, ReferenceIndex, identify, decide } from "./core.mjs";

const TJS = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1";
const here = p => new URL(p, import.meta.url).href;
let loading = null;

async function load(onProgress) {
  const [lib, cfg, meta, buf] = await Promise.all([
    import(TJS),
    fetch(here("config.json")).then(r => r.json()),
    fetch(here("reference.json")).then(r => r.json()),
    fetch(here("reference.f32")).then(r => r.arrayBuffer()),
  ]);
  lib.env.allowLocalModels = false;
  const files = {};
  const progress_callback = e => {
    if (e.status === "progress" && e.total) {
      files[e.file] = [e.loaded, e.total];
      let a = 0, b = 0;
      for (const [l, t] of Object.values(files)) { a += l; b += t; }
      onProgress && onProgress(b ? a / b : 0);
    }
  };
  const [model, processor] = await Promise.all([
    lib.AutoModel.from_pretrained(MODEL_ID, { dtype: DTYPE, progress_callback }),
    lib.AutoProcessor.from_pretrained(MODEL_ID, { progress_callback }),
  ]);
  const items = meta.items.map(it => ({ a: it.id, s: it.s, t: it.t, f: it.f || "natural" }));
  return { lib, cfg, model, processor, index: new ReferenceIndex(new Float32Array(buf), items, meta.dim) };
}

export async function install() {
  const r = await fetch(here("config.json"));
  if (!r.ok) return false;
  const cfg = await r.json();
  window.RockIDModel = {
    version: `DINOv2-small ${cfg.dtype} · ${cfg.reference_photos}`,
    async identify(canvas, onProgress) {
      if (!loading) loading = load(onProgress).catch(e => { loading = null; throw e; });
      const m = await loading;
      const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", 0.92));
      const image = await m.lib.RawImage.fromBlob(blob);
      const v = await embed(m.model, m.processor, image);
      const r = identify(m.index, v, 50, m.cfg.form);
      const d = decide(r.cands, m.cfg.decision);
      return { status: d.status, form: r.form, candidates: d.candidates.map(c => ({ taxon: c.taxon, p: c.p })) };
    },
  };
  return true;
}
