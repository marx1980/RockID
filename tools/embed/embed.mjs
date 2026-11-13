// Embed images listed in a CSV with DINOv2-small (same model and code path as the phone app).
//   node tools/embed/embed.mjs <csv> <id column> <out prefix>
// Writes <out>.f32 (row-major float32) and <out>.json (ids in order + metadata). Reads only
// id, media_url, and (if present) specimen_id / taxon_id: never a ground-truth column.
import fs from "node:fs";
import { AutoModel, AutoProcessor, RawImage, SiglipVisionModel, env } from "@huggingface/transformers";
import { MODEL_ID as APP_MODEL, DTYPE as APP_DTYPE, embed as dinoEmbed } from "../../app/model/core.mjs";

// Overrides for model comparison runs; the app's model is the default.
//   EMBED_MODEL, EMBED_DTYPE: another Hugging Face ONNX model (DINOv2 or SigLIP family)
//   EMBED_MASK: fraction of width and height in the centre painted grey (backdrop-only probe)
const MODEL_ID = process.env.EMBED_MODEL || APP_MODEL;
const DTYPE = process.env.EMBED_DTYPE || APP_DTYPE;
const MASK = Number(process.env.EMBED_MASK || 0);
const SIGLIP = /siglip/i.test(MODEL_ID);

function l2(v) {
  let n = 0;
  for (let i = 0; i < v.length; i++) n += v[i] * v[i];
  n = Math.sqrt(n) || 1;
  const o = new Float32Array(v.length);
  for (let i = 0; i < v.length; i++) o[i] = v[i] / n;
  return o;
}

function maskCentre(img, frac) {
  const { width: W, height: H, channels: C, data } = img;
  const x0 = Math.round(W * (1 - frac) / 2), x1 = W - x0, y0 = Math.round(H * (1 - frac) / 2), y1 = H - y0;
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) for (let c = 0; c < Math.min(C, 3); c++) data[(y * W + x) * C + c] = 128;
  return img;
}

async function embed(model, processor, image) {
  if (MASK > 0) image = maskCentre(image, MASK);
  if (!SIGLIP) return dinoEmbed(model, processor, image);
  const out = await model(await processor(image));
  return l2(out.pooler_output.data);
}

const [csvPath, idCol, outPrefix] = process.argv.slice(2);
const UA = "RockID-embed/0.1 (https://github.com/marx1980/RockID)";
env.allowLocalModels = false;

function parseCsv(text) {
  const rows = []; let row = [], f = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { f += '"'; i++ } else if (c === '"') q = false; else f += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(f); f = ""; }
    else if (c === "\n") { row.push(f); rows.push(row); row = []; f = ""; }
    else if (c !== "\r") f += c;
  }
  if (f || row.length) { row.push(f); rows.push(row); }
  const [h, ...rest] = rows;
  return rest.filter(r => r.length === h.length).map(r => Object.fromEntries(h.map((k, i) => [k, r[i]])));
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
let lastWiki = 0;
async function fetchImage(url) {
  for (let attempt = 0; attempt < 6; attempt++) {
    if (url.includes("wikimedia.org")) {
      const wait = lastWiki + 350 - Date.now();
      if (wait > 0) await sleep(wait);
      lastWiki = Date.now();
    }
    let r;
    try { r = await fetch(url, { headers: { "User-Agent": UA } }); } catch { await sleep(2 ** attempt * 1000); continue; }
    if (r.status === 429 || r.status === 503) {
      await sleep(Math.min(120, Number(r.headers.get("retry-after")) || 2 ** (attempt + 1)) * 1000);
      continue;
    }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return RawImage.fromBlob(await r.blob());
  }
  throw new Error("gave up after retries");
}

const rows = parseCsv(fs.readFileSync(csvPath, "utf8"));
const model = await (SIGLIP ? SiglipVisionModel : AutoModel).from_pretrained(MODEL_ID, { dtype: DTYPE });
const processor = await AutoProcessor.from_pretrained(MODEL_ID);
const items = [], failed = [], chunks = [];
let dim = 0;
for (const [i, r] of rows.entries()) {
  try {
    const v = await embed(model, processor, await fetchImage(r.media_url));
    dim = v.length; chunks.push(v);
    const it = { id: r[idCol] };
    if (r.specimen_id) it.s = r.specimen_id;
    if (r.taxon_id) it.t = r.taxon_id;
    if (r.form && r.form !== "natural") it.f = r.form;
    items.push(it);
  } catch (e) {
    failed.push({ id: r[idCol], error: String(e.message || e) });
  }
  if ((i + 1) % 50 === 0) console.error(`${i + 1}/${rows.length}`);
}
const all = new Float32Array(items.length * dim);
chunks.forEach((v, i) => all.set(v, i * dim));
fs.writeFileSync(`${outPrefix}.f32`, Buffer.from(all.buffer));
fs.writeFileSync(`${outPrefix}.json`, JSON.stringify({ model: MODEL_ID, dtype: DTYPE, mask: MASK, dim, items, failed }));
console.error(`embedded ${items.length}, failed ${failed.length}`);
