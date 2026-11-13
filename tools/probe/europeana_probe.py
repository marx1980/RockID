"""Europeana probe: what the Search API returns for our weak classes (runs in Actions with the key)."""
import json
import os
import sys
import time
from pathlib import Path

import httpx

KEY = os.environ["EUROPEANA_API_KEY"]
API = "https://api.europeana.eu/record/v2/search.json"
UA = "RockID-harvester/0.1 (https://github.com/marx1980/RockID; research reference corpus)"
c = httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True)
out = {}
QUERIES = {
    "magnetite": "magnetite", "biotite": "biotite", "granite": "granite", "marble": "marble", "slate": "slate",
    "chert": "chert", "gneiss": "gneiss", "quartzite": "quartzite", "quartz": "quartz", "pyrite": "pyrite",
    "mineral_specimen": "mineral specimen", "rock_specimen": "rock specimen",
}
for name, q in QUERIES.items():
    time.sleep(0.5)
    try:
        r = c.get(API, params={"wskey": KEY, "query": q, "qf": "TYPE:IMAGE", "reusability": "open", "media": "true", "rows": 30, "profile": "standard"})
        j = r.json()
        items = j.get("items") or []
        out[name] = {"status": r.status_code, "total": j.get("totalResults"), "error": j.get("error"),
                     "items": [{k: it.get(k) for k in ("id", "title", "dcCreator", "dataProvider", "provider", "rights", "edmIsShownBy", "edmPreview", "guid", "type", "dcDescription", "country")} for it in items]}
    except Exception as e:  # noqa: BLE001
        out[name] = {"error": repr(e)}
# does an image link work, and how big
sample = next((it for v in out.values() for it in v.get("items", []) if it.get("edmIsShownBy")), None)
if sample:
    url = sample["edmIsShownBy"][0] if isinstance(sample["edmIsShownBy"], list) else sample["edmIsShownBy"]
    try:
        r = c.get(url, headers={"Range": "bytes=0-5000"})
        out["image_test"] = {"url": url, "status": r.status_code, "ctype": r.headers.get("content-type"), "len": r.headers.get("content-length")}
    except Exception as e:  # noqa: BLE001
        out["image_test"] = {"url": url, "error": repr(e)}
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=str))
print({k: (v.get("total"), v.get("status"), v.get("error")) for k, v in out.items() if k != "image_test"})
