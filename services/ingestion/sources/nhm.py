"""Natural History Museum (London) Data Portal, mineralogy collection (CKAN datastore API, no key).

Every record is one catalogued specimen, so the catalogue number is a reliable specimen ID.
Images carry a per-image licence (so far always CC BY 4.0 -> reference only under our policy).
The portal cannot filter by name substring, so the ~5,000 imaged mineralogy records are fetched
once per run (a handful of polite requests) and matched locally against each taxon's title terms.
"""
import hashlib
import re
import time

import httpx

from services.ingestion.candidates import Candidate
from services.ingestion.licence import propose_usage
from services.ingestion.sources import USER_AGENT, now_iso, other_taxa_named

API = "https://data.nhm.ac.uk/api/3/action/datastore_search"
RESOURCE = "05ff2255-c38a-40c9-b657-4ccb55ab2feb"  # collection specimens (Darwin Core)
SOURCE = "Natural History Museum, London"
PAGE = 500
SPACING = 0.6  # seconds between calls; the portal asks for well under one call per second
MEDIA = "https://data.nhm.ac.uk/media/{asset}"  # server-side resized JPEG; IIIF "!1024,1024" returns 400 for images smaller than that
OBJECT = "https://data.nhm.ac.uk/object/{occurrence}"

# Names that are containers or preparations, not specimens of the rock/mineral named.
_NOT_A_SPECIMEN = re.compile(r"\b(box|bottle|tube|slide|tooth|teeth|jar|vial|glass|plastic|bag|tray)\b", re.I)
# "X in granite", "veins from ...": the named rock is only the host, so the label would be wrong.
_COMPOUND = re.compile(r"\b(in|from|with|on|and|associated|together|bearing|containing|after)\b", re.I)

_cache: dict[str, list[dict]] = {}


def licence_label(url: str) -> str:
    m = re.search(r"creativecommons\.org/(licenses|publicdomain)/([a-z\-]+)/([\d.]+)", url or "")
    if not m:
        return ""
    kind, variant, version = m.groups()
    if kind == "publicdomain":
        return "CC0" if variant == "zero" else "Public domain"
    return f"CC {variant.upper()} {version}"


def fetch_imaged(client: httpx.Client) -> list[dict]:
    """All mineralogy specimen records with at least one still image. Cached per client."""
    key = str(id(client))
    if key in _cache:
        return _cache[key]
    rows: list[dict] = []
    offset = 0
    while True:
        payload = {"resource_id": RESOURCE, "limit": PAGE, "offset": offset,
                   "filters": {"collectionCode": "MIN", "associatedMedia.type": "StillImage"}}
        resp = client.post(API, json=payload, headers={"User-Agent": USER_AGENT}, timeout=120)
        resp.raise_for_status()
        result = resp.json().get("result") or {}
        recs = result.get("records") or []
        rows += recs
        offset += len(recs)
        if not recs or offset >= (result.get("total") or 0):
            break
        time.sleep(SPACING)
    _cache[key] = rows
    return rows


def _name(rec: dict) -> str:
    return (rec.get("scientificName") or "").strip()


def names_taxon(name: str, title_terms: list[str]) -> bool:
    """True when the record is named as the taxon itself (e.g. 'Marble', 'Red granite'), not as a
    container, a mixture, or a hyphenated rock such as 'quartz-porphyry'."""
    if not name or _NOT_A_SPECIMEN.search(name) or _COMPOUND.search(name):
        return False
    return any(re.search(rf"(?<![\w-]){re.escape(t.lower())}(?![\w-])", name.lower()) for t in title_terms)


def search(client: httpx.Client, taxon_id: str, title_terms: list[str], limit: int = 50) -> list[Candidate]:
    matched = [r for r in fetch_imaged(client) if names_taxon(_name(r), title_terms)]
    # Deterministic spread across the collection instead of the first N catalogue numbers.
    matched.sort(key=lambda r: hashlib.sha1((r.get("catalogNumber") or "").encode()).hexdigest())
    out: list[Candidate] = []
    for rec in matched:
        catalogue = rec.get("catalogNumber") or rec.get("occurrenceID") or ""
        name = _name(rec)
        for media in rec.get("associatedMedia") or []:
            if media.get("type") != "StillImage" or media.get("category") != "Specimen" or not media.get("assetID"):
                continue
            licence = licence_label(media.get("license", ""))
            usage, reason = propose_usage(licence)
            where = ", ".join(x for x in (rec.get("locality"), rec.get("country")) if x and x != "Locality Unknown")
            out.append(Candidate(
                candidate_id=f"nhm:{catalogue}:{media['assetID']}",
                taxon_id=taxon_id,
                source_name=SOURCE,
                source_record_id=catalogue,
                title=f"{name} {catalogue}" + (f" ({where})" if where else ""),
                source_url=OBJECT.format(occurrence=rec.get("occurrenceID", "")),
                media_url=MEDIA.format(asset=media["assetID"]),
                author=(media.get("creator") or media.get("rightsHolder") or SOURCE).strip(),
                license=licence,
                license_url=media.get("license", ""),
                specimen_hint=f"nhm:{catalogue}",
                specimen_hint_confidence="high",
                taxon_in_title=True,
                other_taxa_in_title=other_taxa_named(name, taxon_id),
                proposed_usage=usage,
                policy_reason=reason,
                retrieved_at=now_iso(),
            ))
            if len(out) >= limit:
                return out
    return out
