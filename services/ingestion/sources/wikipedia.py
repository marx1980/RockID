"""Images used in the Wikipedia article about a taxon, read through the MediaWiki API.

Files are looked up on Commons (licence and author come from there); files only on Wikipedia
(non-free uploads) are not on Commons and drop out. Thin sections, diagrams and maps are removed
by the review step, not here."""
import httpx

from services.ingestion.candidates import Candidate
from services.ingestion.sources import USER_AGENT
from services.ingestion.sources.commons import API as COMMONS_API, page_to_candidate

WIKI_API = "https://en.wikipedia.org/w/api.php"


def article_files(client: httpx.Client, title: str) -> list[str]:
    params = {"action": "query", "format": "json", "formatversion": "2", "titles": title,
              "prop": "images", "imlimit": "500", "redirects": "1"}
    files: list[str] = []
    while True:
        r = client.get(WIKI_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        r.raise_for_status()
        data = r.json()
        for page in (data.get("query") or {}).get("pages", []):
            files += [i["title"] for i in page.get("images", [])]
        if "continue" not in data:
            return files
        params = {**params, **data["continue"]}


def search(client: httpx.Client, taxon_id: str, articles: list[str], title_terms: list[str], limit: int = 100) -> list[Candidate]:
    out: list[Candidate] = []
    for article in articles:
        files = article_files(client, article)
        for i in range(0, len(files), 40):
            params = {"action": "query", "format": "json", "formatversion": "2",
                      "titles": "|".join(files[i:i + 40]), "prop": "imageinfo",
                      "iiprop": "url|extmetadata|size|mime", "iiurlwidth": "1024"}
            r = client.get(COMMONS_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
            r.raise_for_status()
            for page in (r.json().get("query") or {}).get("pages", []):
                if page.get("missing") or "imageinfo" not in page:
                    continue
                cand = page_to_candidate(page, taxon_id, title_terms, from_article=True)
                if cand:
                    out.append(cand)
        if len(out) >= limit:
            break
    return out[:limit]
