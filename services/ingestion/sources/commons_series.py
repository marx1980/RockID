"""Complete Commons photo series: other views of a specimen already among the candidates.

For each seed (an undecided Commons candidate) the file title minus its view suffix ("Galena-Joplin-03.jpg" ->
"Galena-Joplin") is used as an allimages prefix. A sibling is kept only if it has the same author and the same
specimen hint as the seed, so a series never mixes uploaders. Used to build challenge set C (stones with 2-5
photos); see docs/CHALLENGE_C.md."""
import re

import httpx

from services.ingestion.candidates import Candidate
from services.ingestion.sources import USER_AGENT
from services.ingestion.sources.commons import API, page_to_candidate, specimen_hint

MIN_PREFIX = 10  # shorter prefixes ('Quartz') list other uploaders' files
MAX_SEEDS = 200
PER_SERIES = 20


def series_prefix(title: str) -> str:
    """The specimen part of a file title, in title form (spaces), without 'File:' and the view suffix."""
    stem = re.sub(r"^File:", "", title)
    stem = re.sub(r"\.[a-z0-9]+$", "", stem, flags=re.I)
    stem = re.sub(r"(?:[\s_\-]+(?:\(?\d+\)?|[a-z]|front|back|side|top|detail|close-?up))+$", "", stem, flags=re.I)
    stem = re.sub(r"\d+$", "", stem).strip(" _-")
    return stem.replace("_", " ")


def siblings(client: httpx.Client, seed: Candidate, title_terms: list[str]) -> list[Candidate]:
    prefix = series_prefix(seed.title)
    if len(prefix) < MIN_PREFIX:
        return []
    params = {"action": "query", "format": "json", "formatversion": "2", "generator": "allimages",
              "gaiprefix": prefix, "gailimit": str(PER_SERIES), "prop": "imageinfo",
              "iiprop": "url|extmetadata|size|mime", "iiurlwidth": "1024"}
    r = client.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=40)
    r.raise_for_status()
    out = []
    for page in (r.json().get("query") or {}).get("pages", []):
        if page.get("missing") or "imageinfo" not in page:
            continue
        # The seed already named the taxon, so siblings of the same series count as named.
        cand = page_to_candidate(page, seed.taxon_id, title_terms, from_article=True)
        if cand and cand.author.strip().lower() == seed.author.strip().lower() and cand.specimen_hint == seed.specimen_hint:
            out.append(cand)
    return out


def search(client: httpx.Client, taxon_id: str, seeds: list[Candidate], title_terms: list[str],
           max_seeds: int = MAX_SEEDS) -> list[Candidate]:
    out, done = [], set()
    for seed in seeds:
        if seed.taxon_id != taxon_id or not seed.author.strip():
            continue
        key = (seed.author.strip().lower(), specimen_hint(seed.title))
        if key in done:
            continue
        done.add(key)
        if len(done) > max_seeds:
            break
        out += siblings(client, seed, title_terms)
    return out
