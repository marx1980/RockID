"""Wikimedia Commons file search. Licences vary per file; specimen identity is only guessed."""
import re

import httpx

from services.ingestion.candidates import Candidate
from services.ingestion.licence import propose_usage
from services.ingestion.sources import other_taxa_named, PHOTO_MIMES, USER_AGENT, mentions, now_iso, strip_html

API = "https://commons.wikimedia.org/w/api.php"
SOURCE = "Wikimedia Commons"


def specimen_hint(title: str) -> str:
    """Photo series like 'X-Y-Bisbee-12.jpg' / '...-13.jpg' usually show one specimen.
    Strip extension, trailing view numbers and view words. Low confidence: needs review."""
    stem = re.sub(r"^File:", "", title)
    stem = re.sub(r"\.[a-z0-9]+$", "", stem, flags=re.I)
    stem = re.sub(r"(?:[\s_\-]+(?:\(?\d+\)?|[a-z]|front|back|side|top|detail|close-?up))+$", "", stem, flags=re.I)
    stem = re.sub(r"\d+$", "", stem)
    return "commons:" + re.sub(r"[\s_]+", "-", stem.strip().lower())


def page_to_candidate(page: dict, taxon_id: str, title_terms: list[str], from_article: bool = False) -> Candidate | None:
    """One Commons imageinfo page to a Candidate. from_article: the file illustrates a Wikipedia
    article about the taxon, so it counts as named even when the file title does not say so."""
    info = (page.get("imageinfo") or [{}])[0]
    if info.get("mime") not in PHOTO_MIMES:
        return None
    meta = info.get("extmetadata") or {}
    val = lambda k: strip_html((meta.get(k) or {}).get("value", ""))
    licence = val("LicenseShortName")
    usage, reason = propose_usage(licence)
    title = page.get("title", "")
    in_title = from_article or mentions(title + " " + val("ImageDescription"), title_terms)
    if not in_title:
        usage, reason = "rejected", "taxon not named in title/description"
    return Candidate(
        candidate_id=f"commons:{page.get('pageid')}",
        taxon_id=taxon_id,
        source_name=SOURCE,
        source_record_id=str(page.get("pageid")),
        title=title,
        source_url=info.get("descriptionurl", ""),
        media_url=info.get("thumburl") or info.get("url", ""),
        author=val("Artist"),
        license=licence,
        license_url=val("LicenseUrl"),
        specimen_hint=specimen_hint(title),
        specimen_hint_confidence="low",
        taxon_in_title=in_title,
        other_taxa_in_title=other_taxa_named(title, taxon_id),
        proposed_usage=usage,
        policy_reason=reason,
        retrieved_at=now_iso(),
    )


def search(client: httpx.Client, taxon_id: str, query: str, title_terms: list[str], limit: int = 50) -> list[Candidate]:
    out: list[Candidate] = []
    params = {
        "action": "query", "format": "json", "formatversion": "1",
        "generator": "search", "gsrnamespace": "6", "gsrsearch": f"{query} filetype:bitmap",
        "gsrlimit": str(min(limit, 50)),
        "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": "1024",
    }
    cont: dict = {}
    while len(out) < limit:
        resp = client.get(API, params={**params, **cont}, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        pages = sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
        for page in pages:
            cand = page_to_candidate(page, taxon_id, title_terms)
            if cand:
                out.append(cand)
            if len(out) >= limit:
                break
        cont = data.get("continue") or {}
        if not cont:
            break
    return out
