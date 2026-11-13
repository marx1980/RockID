"""USGS Multimedia Gallery (usgs.gov/media/images). U.S. Government works, marked "Public Domain".

The gallery has no API, so listing pages are crawled once per run for item links; items whose slug names a
taxon are fetched for the image URL and description. Several items are generic "High-definition image ..."
renderings of a "USGS mineral collection" that look machine-generated: they are flagged in the reviewer
note and must be checked by eye before approval."""
import re
import sys
import time

import httpx

from services.ingestion.candidates import Candidate
from services.ingestion.licence import propose_usage
from services.ingestion.sources import USER_AGENT, mentions, now_iso, other_taxa_named, strip_html

SOURCE = "USGS Multimedia Gallery"
BASE = "https://www.usgs.gov"
LISTINGS = [
    "/mission-areas/geology-energy-minerals/multimedia/images",
    "/mission-areas/energy-and-minerals/multimedia/images",
    "/states/virginia/multimedia/images",
]
MAX_PAGES = 60
DELAY = 0.3
ITEM = re.compile(r'href="(?:https://www\.usgs\.gov)?(/media/images/[a-z0-9][a-z0-9\-]*)"')
IMG = re.compile(r'https://d9-wret\.s3[^"\'\s<>]+?\.(?:jpe?g|png)(?:\?[^"\'\s<>]*)?', re.I)
GENERIC = "high-definition image"
_items_cache: dict[str, list[str]] = {}


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=40, follow_redirects=True)
    r.raise_for_status()
    time.sleep(DELAY)
    return r.text


def item_paths(client: httpx.Client) -> list[str]:
    if "all" in _items_cache:
        return _items_cache["all"]
    found: dict[str, None] = {}
    for listing in LISTINGS:
        for page in range(MAX_PAGES):
            try:
                html = _get(client, f"{BASE}{listing}?page={page}")
            except httpx.HTTPError as e:
                print(f"usgs listing {listing} page {page}: {e}", file=sys.stderr)
                break
            new = [p for p in dict.fromkeys(ITEM.findall(html)) if p not in found]
            if not new:
                print(f"usgs listing {listing} page {page}: no new items ({len(html)} bytes)", file=sys.stderr)
                break
            found.update(dict.fromkeys(new))
    _items_cache["all"] = list(found)
    print(f"usgs: {len(found)} item links", file=sys.stderr)
    return _items_cache["all"]


def _meta(html: str, prop: str) -> str:
    m = re.search(rf'<meta[^>]+(?:property|name)="{prop}"[^>]+content="([^"]*)"', html, re.I) or \
        re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="{prop}"', html, re.I)
    return strip_html(m.group(1)) if m else ""


def pick_image(urls: list[str]) -> str:
    """Best photo URL on an item page: the full-width rendition, else an original, else a larger style; never icons."""
    urls = [u for u in dict.fromkeys(urls) if "/thumbnails/" not in u and "/styles/thumbnail/" not in u and "/styles/masonry/" not in u]
    for key in ("/styles/full_width/", "/styles/large/", "/styles/medium/", "/styles/teaser/"):
        hit = next((u for u in urls if key in u), None)
        if hit:
            return hit
    return urls[0] if urls else ""


def parse_item(html: str, path: str, taxon_id: str, terms: list[str]) -> Candidate | None:
    text = strip_html(html)
    if "public domain" not in text.lower():
        return None
    imgs = IMG.findall(html)
    if not imgs or not pick_image(imgs):
        return None
    media = pick_image(imgs)
    title = _meta(html, "og:title") or (re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I) or [None, ""])[1]
    title = strip_html(title).replace(" | U.S. Geological Survey", "").strip()
    desc = _meta(html, "og:description") or _meta(html, "description")
    slug = path.rsplit("/", 1)[-1]
    usage, reason = propose_usage("Public domain")
    named = mentions(f"{title} {slug.replace('-', ' ')}", terms)
    if not named:
        usage, reason = "rejected", "taxon not named in title"
    generic = GENERIC in desc.lower() or GENERIC in text.lower()[:4000]
    return Candidate(
        candidate_id=f"usgs:{slug}",
        taxon_id=taxon_id,
        source_name=SOURCE,
        source_record_id=slug,
        title=title or slug,
        source_url=f"{BASE}{path}",
        media_url=media,
        author=SOURCE,
        license="Public domain",
        license_url="https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits",
        specimen_hint=f"usgs:{slug}",
        specimen_hint_confidence="high",
        taxon_in_title=named,
        other_taxa_in_title=other_taxa_named(title, taxon_id),
        proposed_usage=usage,
        policy_reason=reason,
        retrieved_at=now_iso(),
        reviewer_note="possible machine-generated rendering: check by eye" if generic else "",
    )


def search(client: httpx.Client, taxon_id: str, terms: list[str], limit: int = 100) -> list[Candidate]:
    out: list[Candidate] = []
    for path in item_paths(client):
        if len(out) >= limit:
            break
        if not mentions(path.rsplit("/", 1)[-1].replace("-", " "), terms):
            continue
        try:
            html = _get(client, f"{BASE}{path}")
        except httpx.HTTPError as e:
            print(f"usgs item {path}: {e}", file=sys.stderr)
            continue
        cand = parse_item(html, path, taxon_id, terms)
        if not cand:
            print(f"usgs item {path}: not parsed (public domain {'public domain' in strip_html(html).lower()}, images {len(IMG.findall(html))}, {len(html)} bytes)", file=sys.stderr)
        if cand:
            out.append(cand)
    return out
