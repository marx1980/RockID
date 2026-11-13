import html
import re
from datetime import datetime, timezone

USER_AGENT = "RockID-harvester/0.1 (https://github.com/marx1980/RockID; research reference corpus)"
PHOTO_MIMES = {"image/jpeg", "image/png", "image/webp"}


def strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def mentions(text: str, terms: list[str]) -> bool:
    low = (text or "").lower()
    return any(t.lower() in low for t in terms)


def other_taxa_named(text: str, own_taxon: str) -> str:
    from packages.taxonomy.loader import load_taxonomy

    low = (text or "").lower()
    hits = []
    for tid, taxon in load_taxonomy().items():
        name = taxon.canonical_name.lower()
        if tid != own_taxon and re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", low):
            hits.append(tid)
    return "|".join(sorted(hits))


def licence_label(url: str) -> str:
    """Creative Commons licence URL -> the short label our policy understands ('CC BY 4.0', 'CC0')."""
    m = re.search(r"creativecommons\.org/(licenses|publicdomain)/([a-z\-]+)/([\d.]+)", url or "")
    if not m:
        return ""
    kind, variant, version = m.groups()
    if kind == "publicdomain":
        return "CC0" if variant == "zero" else "Public domain"
    return f"CC {variant.upper()} {version}"
