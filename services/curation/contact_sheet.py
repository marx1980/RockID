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
from services.ingestion.http import get_with_backoff

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
        r = get_with_backoff(client, url, attempts=5, min_interval=0, sleep=sleep, timeout=40)
        if r is None:
            continue
        STATUS[str(r.status_code)] = STATUS.get(str(r.status_code), 0) + 1
        if r.status_code != 200:
            continue
        try:
            im = Image.open(BytesIO(r.content))
            im.load()
            return im.convert("RGB")
        except Exception:
            continue
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


def reviewed_ids(review_csv: str | Path) -> set[str]:
    import csv
    with Path(review_csv).open(newline="", encoding="utf-8") as fh:
        return {r["candidate_id"] for r in csv.DictReader(fh)}


def diversify(cands, per_author=0, per_taxon=0, skip_authors=()):
    """Cap each author per taxon, then round-robin across authors up to per_taxon, so one photographer cannot fill a taxon."""
    out: list[Candidate] = []
    by_taxon: dict[str, dict[str, list[Candidate]]] = {}
    for c in cands:
        a = (c.author or "").strip()
        if any(k.lower() in a.lower() for k in skip_authors):
            continue
        by_taxon.setdefault(c.taxon_id, {}).setdefault(a, []).append(c)
    for taxon, authors in by_taxon.items():
        pools = [v[:per_author] if per_author else v for v in authors.values()]
        picked: list[Candidate] = []
        i = 0
        while any(i < len(p) for p in pools) and not (per_taxon and len(picked) >= per_taxon):
            for p in pools:
                if i < len(p) and not (per_taxon and len(picked) >= per_taxon):
                    picked.append(p[i])
            i += 1
        out.extend(picked)
    out.sort(key=lambda c: (c.taxon_id, c.specimen_hint, c.candidate_id))
    return out


def build(candidates_csv: str | Path, out_dir: str | Path, client: httpx.Client, workers: int = 6,
          commons_delay: float = 0.25, skip: set[str] | None = None, prefix: str = "", only_source: str = "",
          per_author: int = 0, per_taxon: int = 0, skip_authors: tuple = ()) -> dict:
    """`skip` = candidate ids already reviewed (a later review round only sees new candidates);
    `prefix` keeps sheet names of different rounds apart."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cands = [c for c in read_candidates(candidates_csv) if c.proposed_usage != "rejected" and c.candidate_id not in (skip or set()) and only_source in c.source_name]
    cands.sort(key=lambda c: (c.taxon_id, c.specimen_hint, c.candidate_id))
    if per_author or per_taxon:
        cands = diversify(cands, per_author, per_taxon, skip_authors)
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
            name = f"{prefix}{taxon}-{s // PER_SHEET + 1}"
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
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("out")
    ap.add_argument("--skip-reviewed", help="agent_review.csv; its candidates are left out")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--only-source", default="", help="keep candidates whose source name contains this text")
    ap.add_argument("--per-author", type=int, default=0, help="max candidates per author per taxon")
    ap.add_argument("--per-taxon", type=int, default=0, help="max candidates per taxon (round-robin across authors)")
    ap.add_argument("--skip-authors", default="", help="comma list of author substrings to leave out")
    a = ap.parse_args()
    with httpx.Client(follow_redirects=True) as client:
        print(build(a.candidates, a.out, client, skip=reviewed_ids(a.skip_reviewed) if a.skip_reviewed else None, prefix=a.prefix,
                    only_source=a.only_source,
                    per_author=a.per_author, per_taxon=a.per_taxon, skip_authors=tuple(x for x in a.skip_authors.split(",") if x)))
