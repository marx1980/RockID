"""Europeana probe 2: full record fields for a few geology hits (specimen identifiers, creators)."""
import json, os, sys, time
from pathlib import Path
import httpx

KEY = os.environ["EUROPEANA_API_KEY"]
API = "https://api.europeana.eu/record/v2/search.json"
c = httpx.Client(headers={"User-Agent": "RockID-harvester/0.1 (https://github.com/marx1980/RockID; research reference corpus)"}, timeout=60)
out = {}
for name, q in {"magnetite": "magnetite", "granite": "granite", "biotite": "biotite"}.items():
    time.sleep(0.5)
    r = c.get(API, params={"wskey": KEY, "query": q, "qf": ["TYPE:IMAGE", "DATA_PROVIDER:\"The Estonian Museum of Natural History\""], "reusability": "open", "media": "true", "rows": 4, "profile": "rich"})
    out[name] = r.json().get("items")
# counts by provider for the weak classes
counts = {}
for q in ("magnetite", "biotite", "granite", "marble", "slate", "chert", "gneiss", "quartzite", "pyrite", "malachite", "hematite", "muscovite"):
    time.sleep(0.5)
    r = c.get(API, params={"wskey": KEY, "query": q, "qf": "TYPE:IMAGE", "reusability": "open", "media": "true", "rows": 0, "profile": "facets", "facet": "DATA_PROVIDER", "f.DATA_PROVIDER.facet.limit": 8})
    j = r.json()
    counts[q] = {"total": j.get("totalResults"), "facets": [(f.get("fields") or []) for f in (j.get("facets") or [])][:1]}
out["counts"] = counts
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(counts)[:3000])
