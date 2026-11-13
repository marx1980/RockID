"""One-off probe of the NHM Data Portal API: dumps schema and a few mineralogy records so the
harvester can be written against real field names. Runs in Actions (the sandbox cannot reach NHM)."""
import json
import sys
import time
from pathlib import Path

import httpx

BASES = ["https://data.nhm.ac.uk/api/3/action", "https://data.nhm.ac.uk/is/api/3/action"]
UA = "RockID-harvester/0.1 (https://github.com/marx1980/RockID; research reference corpus)"
out = {}
client = httpx.Client(headers={"User-Agent": UA}, timeout=90, follow_redirects=True)


def call(action, params=None, payload=None):
    last = None
    for base in BASES:
        try:
            time.sleep(0.5)
            r = client.post(f"{base}/{action}", json=payload) if payload is not None else client.get(f"{base}/{action}", params=params)
            last = {"base": base, "status": r.status_code}
            if r.status_code == 200:
                return {**last, "json": r.json()}
        except Exception as e:  # noqa: BLE001
            last = {"base": base, "error": repr(e)}
    return last


pkg = call("package_show", {"id": "collection-specimens"})
out["package_show"] = pkg
resources = (((pkg or {}).get("json") or {}).get("result") or {}).get("resources") or []
out["resources"] = [{k: r.get(k) for k in ("id", "name", "format", "description", "license_id")} for r in resources]
out["licence"] = {k: (((pkg or {}).get("json") or {}).get("result") or {}).get(k) for k in ("license_id", "license_title")}
specimen = next((r["id"] for r in resources if "specimen" in (r.get("name") or "").lower()), resources[0]["id"] if resources else None)
out["specimen_resource"] = specimen
if specimen:
    out["fields"] = call("datastore_search", {"resource_id": specimen, "limit": 1})
    for name, payload in {
        "min_quartz_media": {"resource_id": specimen, "q": "quartz", "filters": {"collectionCode": "MIN"}, "limit": 5},
        "min_any": {"resource_id": specimen, "filters": {"collectionCode": "MIN"}, "limit": 3},
        "facet_collection": {"resource_id": specimen, "limit": 0, "facets": ["collectionCode", "typeStatus"]},
    }.items():
        out[name] = call("datastore_search", payload=payload)
    # Multimedia often lives in a separate resource; list every datastore-active resource of every NHM package that mentions images
    out["search_media"] = call("package_search", {"q": "specimen images mineralogy", "rows": 10})
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=str)[:900000])
print("ok", len(json.dumps(out, default=str)))
