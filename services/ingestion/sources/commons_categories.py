"""Files in hand-picked Wikimedia Commons categories (for example "Granite samples").

Categories ending in "+" also take their direct subcategories (one level), minus names that point at
diagrams, thin sections, buildings or quarries. Licence and author come from the file page."""
import httpx

from services.ingestion.candidates import Candidate
from services.ingestion.sources import USER_AGENT
from services.ingestion.sources.commons import API, page_to_candidate

SKIP_SUBCAT = ("thin section", "diagram", "map", "quarr", "mine", "building", "architecture", "art", "sculpt", "statue",
               "construction", "formation", "cliff", "outcrop", "boulder", "gravestone", "monument", "church", "castle",
               "bridge", "wall", "road", "paving", "tors", "fossil", "textbook", "illustration", "history", "people",
               "by country", "by location")
MAX_SUBCATS = 40
PER_CATEGORY = 300


def _get(client: httpx.Client, params: dict) -> dict:
    r = client.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=40)
    r.raise_for_status()
    return r.json()


def subcategories(client: httpx.Client, category: str) -> list[str]:
    data = _get(client, {"action": "query", "format": "json", "formatversion": "2", "list": "categorymembers",
                         "cmtitle": category, "cmtype": "subcat", "cmlimit": "200"})
    names = [m["title"] for m in (data.get("query") or {}).get("categorymembers", [])]
    return [n for n in names if not any(w in n.lower() for w in SKIP_SUBCAT)][:MAX_SUBCATS]


def category_files(client: httpx.Client, category: str, taxon_id: str, title_terms: list[str], limit: int = PER_CATEGORY) -> list[Candidate]:
    out: list[Candidate] = []
    params = {"action": "query", "format": "json", "formatversion": "2", "generator": "categorymembers",
              "gcmtitle": category, "gcmtype": "file", "gcmlimit": "50", "prop": "imageinfo",
              "iiprop": "url|extmetadata|size|mime", "iiurlwidth": "1024"}
    while len(out) < limit:
        data = _get(client, params)
        for page in (data.get("query") or {}).get("pages", []):
            if page.get("missing") or "imageinfo" not in page:
                continue
            cand = page_to_candidate(page, taxon_id, title_terms, from_article=True)
            if cand:
                out.append(cand)
        if "continue" not in data:
            break
        params = {**params, **data["continue"]}
    return out[:limit]


def search(client: httpx.Client, taxon_id: str, categories: list[str], title_terms: list[str]) -> list[Candidate]:
    out: list[Candidate] = []
    for spec in categories:
        recurse = spec.endswith("+")
        root = spec.rstrip("+")
        names = [root] + (subcategories(client, root) if recurse else [])
        for name in names:
            out += category_files(client, name, taxon_id, title_terms)
    return out
