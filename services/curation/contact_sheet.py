"""Numbered thumbnail contact sheets per taxon, for agent visual review.

  python -m services.curation.contact_sheet data_manifests/candidates/candidates.csv sheets/

Writes sheets/<taxon>-<n>.jpg, sheets/index.json (sheet -> tile number -> candidate_id)
and sheets/ATTRIBUTION.md. Thumbnails are small, low-quality review copies only.
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from services.ingestion.candidates import Candidate, read_candidates
from services.ingestion.sources import USER_AGENT

COLS, ROWS, TILE, HEADER = 6, 5, 200, 44
PER_SHEET = COLS * ROWS


def thumb_url(url: str, size: int = 330) -> str:
    if "ids.si.edu" in url:
        import re
        return re.sub(r"max=\d+", f"max={size}", url) if "max=" in url else f"{url}&max={size}"
    if "upload.wikimedia.org" in url:
        import re
        base = url.split("?")[0]
        if re.search(r"/\d+px-", base):
            return re.sub(r"/\d+px-", f"/{size}px-", base)
        m = re.match(r"^(https://upload\.wikimedia\.org/wikipedia/commons)/([0-9a-f]/[0-9a-f]{2})/([^/]+)$", base)
        if m:
            return f"{m[1]}/thumb/{m[2]}/{m[3]}/{size}px-{m[3]}"
        return base
    return url


def _font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


STATUS: dict[str, int] = {}


def fetch(client: httpx.Client, c: Candidate, sleep=time.sleep) -> Image.Image | None:
    for url in (thumb_url(c.media_url), c.media_url):
        for attempt in range(5):
            try:
                r = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=40)
            except httpx.HTTPError:
                sleep(2 ** attempt)
                continue
            STATUS[str(r.status_code)] = STATUS.get(str(r.status_code), 0) + 1
            if r.status_code in (429, 503):
                sleep(float(r.headers.get("retry-after") or 2 ** attempt))
                continue
            if r.status_code != 200:
                break
            try:
                im = Image.open(BytesIO(r.content))
                im.load()
                return im.convert("RGB")
            except Exception:
                break
    return None


def render(title: str, tiles: list[tuple[int, Image.Image | None]]) -> Image.Image:
    sheet = Image.new("RGB", (COLS * TILE, HEADER + ROWS * TILE), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), title, fill=(255, 255, 255), font=_font(24))
    big = _font(26)
    for k, (num, im) in enumerate(tiles):
        x, y = (k % COLS) * TILE, HEADER + (k // COLS) * TILE
        if im is None:
            d.rectangle([x + 2, y + 2, x + TILE - 3, y + TILE - 3], outline=(160, 40, 40), width=3)
            d.text((x + 60, y + 90), "missing", fill=(200, 80, 80), font=_font(20))
        else:
            im = im.copy()
            im.thumbnail((TILE - 4, TILE - 4))
            sheet.paste(im, (x + (TILE - im.width) // 2, y + (TILE - im.height) // 2))
        d.rectangle([x, y, x + 46, y + 32], fill=(255, 220, 0))
        d.text((x + 4, y + 1), str(num), fill=(0, 0, 0), font=big)
        d.rectangle([x, y, x + TILE - 1, y + TILE - 1], outline=(60, 60, 60))
    return sheet


def build(candidates_csv: str | Path, out_dir: str | Path, client: httpx.Client, workers: int = 6,
          commons_delay: float = 0.25) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cands = [c for c in read_candidates(candidates_csv) if c.proposed_usage != "rejected"]
    cands.sort(key=lambda c: (c.taxon_id, c.specimen_hint, c.candidate_id))
    by_taxon: dict[str, list[Candidate]] = {}
    for c in cands:
        by_taxon.setdefault(c.taxon_id, []).append(c)

    # Wikimedia throttles parallel thumbnail requests: fetch Commons one at a time, others in parallel.
    commons = [c for c in cands if "wikimedia.org" in c.media_url]
    others = [c for c in cands if "wikimedia.org" not in c.media_url]
    images: dict[str, Image.Image | None] = {}
    with ThreadPoolExecutor(workers) as pool:
        images.update(zip((c.candidate_id for c in others), pool.map(lambda c: fetch(client, c), others)))
    for c in commons:
        images[c.candidate_id] = fetch(client, c)
        time.sleep(commons_delay)

    index: dict[str, dict[str, str]] = {}
    attribution = ["# Review thumbnails: attribution", "",
                   "Low-resolution copies for internal review only; each belongs to its author under the listed licence.", "",
                   "| sheet | # | author | licence | source |", "|---|---|---|---|---|"]
    for taxon, items in by_taxon.items():
        for s in range(0, len(items), PER_SHEET):
            chunk = items[s:s + PER_SHEET]
            name = f"{taxon}-{s // PER_SHEET + 1}"
            tiles = [(s + k + 1, images[c.candidate_id]) for k, c in enumerate(chunk)]
            render(f"{taxon}  {s + 1}-{s + len(chunk)} of {len(items)}", tiles).save(out / f"{name}.jpg", quality=82)
            index[name] = {str(s + k + 1): c.candidate_id for k, c in enumerate(chunk)}
            for k, c in enumerate(chunk):
                attribution.append(f"| {name} | {s + k + 1} | {c.author.replace('|', '/')} | {c.license} | {c.source_url} |")
    (out / "index.json").write_text(json.dumps(index, indent=1))
    (out / "ATTRIBUTION.md").write_text("\n".join(attribution) + "\n")
    missing = sorted(cid for cid, im in images.items() if im is None)
    (out / "missing.json").write_text(json.dumps(missing))
    (out / "http_status.json").write_text(json.dumps(STATUS))
    return {"sheets": len(index), "candidates": len(cands), "missing": len(missing)}


if __name__ == "__main__":
    with httpx.Client(follow_redirects=True) as client:
        print(build(sys.argv[1], sys.argv[2], client))
