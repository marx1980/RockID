"""Second NHM probe: how to filter to records with images, and how to get a sensibly sized image."""
import json
import sys
import time
from pathlib import Path

import httpx

BASE = "https://data.nhm.ac.uk/api/3/action"
RES = "05ff2255-c38a-40c9-b657-4ccb55ab2feb"
UA = "RockID-harvester/0.1 (https://github.com/marx1980/RockID; research reference corpus)"
c = httpx.Client(headers={"User-Agent": UA}, timeout=90, follow_redirects=False)
out = {}


def search(name, payload):
    time.sleep(0.6)
    try:
        r = c.post(f"{BASE}/datastore_search", json={"resource_id": RES, **payload})
        j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        res = j.get("result") or {}
        out[name] = {"status": r.status_code, "total": res.get("total"), "error": j.get("error"),
                     "records": [{k: x.get(k) for k in ("catalogNumber", "scientificName", "petrologyType", "locality", "country", "associatedMediaCount", "associatedMedia")} for x in (res.get("records") or [])[:3]]}
    except Exception as e:  # noqa: BLE001
        out[name] = {"error": repr(e)}


search("has_media_type", {"filters": {"collectionCode": "MIN", "associatedMedia.type": "StillImage"}, "limit": 3})
search("has_media_category", {"filters": {"collectionCode": "MIN", "associatedMedia.category": "Specimen"}, "limit": 3})
search("has_image_flag", {"filters": {"collectionCode": "MIN", "_has_image": "true"}, "limit": 3})
search("count1", {"filters": {"collectionCode": "MIN", "associatedMediaCount": 1}, "limit": 3})
search("quartz_media", {"filters": {"collectionCode": "MIN", "scientificName": "Quartz", "associatedMedia.type": "StillImage"}, "limit": 5})
search("granite_q", {"q": "granite", "filters": {"collectionCode": "MIN", "associatedMedia.type": "StillImage"}, "limit": 5})
for name in ("Quartz", "Calcite", "Pyrite", "Fluorite", "Galena", "Biotite", "Magnetite", "Malachite", "Azurite", "Gypsum", "Marble", "Granite", "Slate", "Chert", "Basalt"):
    search(f"count_{name}", {"filters": {"collectionCode": "MIN", "scientificName": name, "associatedMedia.type": "StillImage"}, "limit": 1})
# image sizing
asset = None
for k in ("has_media_type", "quartz_media"):
    for rec in out.get(k, {}).get("records", []):
        for m in rec.get("associatedMedia") or []:
            asset = asset or m.get("assetID")
out["asset"] = asset
if asset:
    tests = [f"https://data.nhm.ac.uk/media/{asset}", f"https://data.nhm.ac.uk/media/{asset}?width=1024"]
    for u in tests:
        time.sleep(0.6)
        try:
            r = c.get(u, headers={"Range": "bytes=0-2000"})
            out[f"get {u}"] = {"status": r.status_code, "headers": dict(r.headers)}
        except Exception as e:  # noqa: BLE001
            out[f"get {u}"] = {"error": repr(e)}
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, default=str)[:3000])
