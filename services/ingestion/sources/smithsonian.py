"""Smithsonian Open Access, NMNH Mineral Sciences. Each record is one catalogued specimen,
so the record ID is a reliable specimen ID. Only media marked CC0 are kept."""
import httpx

from services.ingestion.candidates import Candidate
from services.ingestion.licence import propose_usage
from services.ingestion.sources import other_taxa_named, USER_AGENT, mentions, now_iso

API = "https://api.si.edu/openaccess/api/v1.0/search"
SOURCE = "Smithsonian NMNH Mineral Sciences"
UNIT = "NMNHMINSCI"
PAGE = 100


def _freetext(content: dict, field: str, labels: tuple[str, ...]) -> str:
    for item in (content.get("freetext") or {}).get(field, []) or []:
        if any(l.lower() in (item.get("label") or "").lower() for l in labels):
            return item.get("content", "")
    return ""


def search(
    client: httpx.Client, taxon_id: str, query: str, title_terms: list[str],
    limit: int = 50, api_key: str = "DEMO_KEY",
) -> list[Candidate]:
    out: list[Candidate] = []
    start = 0
    while len(out) < limit:
        params = {
            "q": f"{query} AND unit_code:{UNIT} AND online_media_type:Images",
            "start": str(start), "rows": str(PAGE), "api_key": api_key,
        }
        resp = client.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
        resp.raise_for_status()
        rows = ((resp.json().get("response") or {}).get("rows")) or []
        for row in rows:
            content = row.get("content") or {}
            dnr = content.get("descriptiveNonRepeating") or {}
            if (dnr.get("unit_code") or row.get("unitCode")) != UNIT:
                continue
            title = (dnr.get("title") or {}).get("content") or row.get("title", "")
            in_title = mentions(title, title_terms)
            record_id = dnr.get("record_ID", row.get("id", ""))
            author = _freetext(content, "name", ("photographer",)) or SOURCE
            for media in (dnr.get("online_media") or {}).get("media", []) or []:
                if media.get("type") != "Images" or (media.get("usage") or {}).get("access") != "CC0":
                    continue
                usage, reason = propose_usage("CC0")
                if not in_title:
                    usage, reason = "rejected", "taxon not named in title"
                url = media.get("content", "")
                out.append(Candidate(
                    candidate_id=f"si:{record_id}:{media.get('idsId', url)}",
                    taxon_id=taxon_id,
                    source_name=SOURCE,
                    source_record_id=record_id,
                    title=title,
                    source_url=dnr.get("record_link", ""),
                    media_url=f"{url}&max=1024" if "deliveryService" in url else url,
                    author=author,
                    license="CC0",
                    license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                    specimen_hint=f"si:{record_id}",
                    specimen_hint_confidence="high",
                    taxon_in_title=in_title,
                    other_taxa_in_title=other_taxa_named(title, taxon_id),
                    proposed_usage=usage,
                    policy_reason=reason,
                    retrieved_at=now_iso(),
                ))
                if len(out) >= limit:
                    return out
        if len(rows) < PAGE:
            break
        start += PAGE
    return out
