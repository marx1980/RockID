"""Third NHM probe: list every mineralogy record with an image (compact) and test IIIF sizing."""
import json
import sys
import time
from pathlib import Path

import httpx

BASE = "https://data.nhm.ac.uk/api/3/action"
RES = "05ff2255-c38a-40c9-b657-4ccb55ab2feb"
UA = "RockID-harvester/0.1 (https://github.com/marx1980/RockID; research reference corpus)"
c = httpx.Client(headers={"User-Agent": UA}, timeout=120, follow_redirects=True)
KEEP = ("catalogNumber", "scientificName", "currentScientificName", "identificationAsRegistered", "petrologyType", "petrologySubtype",
        "mineralComplex", "locality", "country", "kindOfObject", "associatedMedia", "occurrenceID", "recordedBy", "donorName")
rows, offset, total = [], 0, None
while True:
    time.sleep(0.6)
    r = c.post(f"{BASE}/datastore_search", json={"resource_id": RES, "filters": {"collectionCode": "MIN", "associatedMedia.type": "StillImage"},
                                                 "limit": 500, "offset": offset})
    res = r.json()["result"]
    total = res["total"]
    recs = res["records"]
    rows += [{k: x.get(k) for k in KEEP} for x in recs]
    offset += len(recs)
    if not recs or offset >= total:
        break
out = {"total": total, "rows": rows}
asset = tiff = None
for x in rows:
    for m in x.get("associatedMedia") or []:
        if m.get("format") == "image/jpeg" and not asset:
            asset = m["assetID"]
        if m.get("format") == "image/tiff" and not tiff:
            tiff = m["assetID"]
tests = {}
for label, a in (("jpeg", asset), ("tiff", tiff)):
    if not a:
        continue
    for suffix in ("", "/full/!1024,1024/0/default.jpg", "/full/1024,/0/default.jpg", "/full/max/0/default.jpg", "/info.json"):
        u = f"https://data.nhm.ac.uk/media/{a}{suffix}"
        time.sleep(0.6)
        try:
            rr = c.get(u)
            body = rr.content
            tests[f"{label} {suffix or '(plain)'}"] = {"status": rr.status_code, "ctype": rr.headers.get("content-type"), "bytes": len(body),
                                                        "head": body[:300].decode("latin1") if "json" in (rr.headers.get("content-type") or "") else ""}
        except Exception as e:  # noqa: BLE001
            tests[f"{label} {suffix or '(plain)'}"] = {"error": repr(e)}
out["tests"] = tests
Path(sys.argv[1]).write_text(json.dumps(out, default=str))
print(total, len(rows), json.dumps(tests, indent=1)[:2500])
