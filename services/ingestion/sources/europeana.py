"""Europeana Search API (free key in EUROPEANA_API_KEY). Aggregates European museum collections.

Only records Europeana itself marks as openly reusable are requested (CC0, public domain mark,
CC BY, CC BY-SA); the licence of each image is still read from the record and run through our
policy. Mixed object types (archaeology, ethnography, herbaria) share the index, so a record is kept
only if a title names the taxon itself, and the visual review does the rest. One record is one
catalogued object; its Europeana id is the specimen hint (low confidence: a specimen may have several records).
"""
import re
import time

import httpx

from services.ingestion.candidates import Candidate
from services.ingestion.licence import propose_usage
from services.ingestion.sources import USER_AGENT, licence_label, now_iso, other_taxa_named

API = "https://api.europeana.eu/record/v2/search.json"
PAGE = 100
SPACING = 0.4
# Providers whose "granite"/"marble"/"slate" objects are carvings, tools or plants, not specimens.
_NOT_GEOLOGY = re.compile(r"antiquit|archaeolog|ethnograph|librar|archive|botanic|herbari|heritage|kew\b|garden|fotothek|"
                          r"inscription|corpus|castle|church|cultur|folk|textile|art\b|kunst", re.I)
_COMPOUND = re.compile(r"\b(in|from|with|on|and|associated|bearing|containing|quarry|building|statue|monument|portrait|view)\b", re.I)


def names_taxon(titles: list[str], terms: list[str]) -> str:
    """The first title that names the taxon as the object itself, else ''."""
    for title in titles:
        t = (title or "").strip()
        if not t or _COMPOUND.search(t):
            continue
        if any(re.search(rf"(?<![\w-]){re.escape(x.lower())}(?![\w-])", t.lower()) for x in terms):
            return t
    return ""


def search(client: httpx.Client, taxon_id: str, title_terms: list[str], limit: int, api_key: str) -> list[Candidate]:
    query = "title:(" + " OR ".join(f'"{t}"' for t in title_terms) + ")"
    params = {"wskey": api_key, "query": query, "qf": "TYPE:IMAGE", "reusability": "open", "media": "true",
              "rows": str(PAGE), "profile": "standard", "cursor": "*"}
    out: list[Candidate] = []
    seen: set[str] = set()
    for _ in range(40):  # hard stop on paging
        resp = client.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items") or []:
            provider = (item.get("dataProvider") or [""])[0]
            titles = item.get("title") or []
            name = names_taxon(titles, title_terms)
            image = (item.get("edmIsShownBy") or [""])[0]
            record = item.get("id", "")
            if not (name and image and record) or record in seen or _NOT_GEOLOGY.search(provider):
                continue
            seen.add(record)
            licence = licence_label((item.get("rights") or [""])[0])
            usage, reason = propose_usage(licence)
            if usage == "rejected":  # not openly reusable under our policy: do not even propose it
                continue
            source = f"Europeana: {provider}"
            creator = ((item.get("dcCreator") or [""])[0] or "").strip()
            out.append(Candidate(
                candidate_id=f"eu:{record}",
                taxon_id=taxon_id,
                source_name=source,
                source_record_id=record,
                title=name + (f" ({provider})" if provider else ""),
                source_url=f"https://www.europeana.eu/item{record}",
                media_url=image,
                author=creator or source,
                license=licence,
                license_url=(item.get("rights") or [""])[0],
                specimen_hint=f"eu:{record}",
                specimen_hint_confidence="low",
                taxon_in_title=True,
                other_taxa_in_title=other_taxa_named(name, taxon_id),
                proposed_usage=usage,
                policy_reason=reason,
                retrieved_at=now_iso(),
            ))
            if len(out) >= limit:
                return out
        cursor = data.get("nextCursor")
        if not cursor or not (data.get("items") or []):
            break
        params = {**params, "cursor": cursor}
        time.sleep(SPACING)
    return out
