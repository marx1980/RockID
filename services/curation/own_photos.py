"""Add photos labelled in the app (Settings > Export) to the reference set.

  python -m services.curation.own_photos rockid-labels-2026-11-14.json [more.json ...]

Each item has the photo (a 1024 px JPEG from the phone's canvas, so no EXIF or location), the label the
owner chose (a taxon id, or `other` with a name) and what the app had answered. Photos labelled with a
taxon become reference rows (source "Own photos", licence "Own work"). Photos labelled `other` are kept
in data_manifests/own_photos/ood.csv as out-of-distribution cases and never enter the reference set.
Photos taken on the same day of the same taxon count as one specimen."""
import base64
import csv
import hashlib
import io
import json
import sys
from datetime import date
from pathlib import Path

import imagehash
from PIL import Image

from packages.taxonomy.loader import load_taxonomy

ROOT = Path(__file__).resolve().parents[2]
OWN = ROOT / "data_manifests/own_photos"
REFERENCE = ROOT / "data_manifests/reference/reference.csv"
SOURCE = "Own photos (Marko)"
LICENSE = "Own work"
FORMS = {"natural", "tumbled", "polished"}
OOD_COLUMNS = ["asset_id", "other_name", "taken_at", "predicted_status", "predicted_top1", "media_url"]


def _decode(photo: str) -> bytes:
    return base64.b64decode(photo.split(",", 1)[1])


def ingest(export_paths: list[str], root: Path = ROOT) -> dict:
    own, ref_csv = root / "data_manifests/own_photos", root / "data_manifests/reference/reference.csv"
    (own / "img").mkdir(parents=True, exist_ok=True)
    taxa = set(load_taxonomy())
    with ref_csv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields, ref_rows = reader.fieldnames, list(reader)
    known_ids = {r["asset_id"] for r in ref_rows}
    known_sha = {r["sha256"] for r in ref_rows}
    ood_path = own / "ood.csv"
    ood_rows = list(csv.DictReader(ood_path.open(newline="", encoding="utf-8"))) if ood_path.exists() else []
    ood_ids = {r["asset_id"] for r in ood_rows}
    added = {"reference": 0, "ood": 0, "skipped": 0}
    for path in export_paths:
        data = json.loads(Path(path).read_text())
        if data.get("app") != "rockid-labels":
            raise SystemExit(f"{path}: not a RockID label export")
        for it in data["items"]:
            aid = f"own:{it['id']}"
            if aid in known_ids or aid in ood_ids:
                added["skipped"] += 1
                continue
            raw = _decode(it["photo"])
            img = Image.open(io.BytesIO(raw)).convert("RGB")  # re-encoded: no metadata survives
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=90)
            sha = hashlib.sha256(buf.getvalue()).hexdigest()
            if sha in known_sha:
                added["skipped"] += 1
                continue
            rel = f"data_manifests/own_photos/img/{it['id']}.jpg"
            (root / rel).write_bytes(buf.getvalue())
            taken = (it.get("at") or "")[:10] or date.today().isoformat()
            top = ((it.get("predicted") or {}).get("top") or [{}])[0].get("taxon", "")
            if it["truth"] in taxa:
                form = it.get("form") if it.get("form") in FORMS else "natural"
                ref_rows.append({"asset_id": aid, "taxon_id": it["truth"], "specimen_id": f"own:{it['truth']}:{taken}",
                                 "source_name": SOURCE, "source_url": "", "author": "Marko", "license": LICENSE,
                                 "retrieval_date": taken, "usage_decision": "allowed_train", "sha256": sha,
                                 "phash": str(imagehash.phash(img)), "media_url": rel, "form": form})
                known_ids.add(aid)
                known_sha.add(sha)
                added["reference"] += 1
            else:
                ood_rows.append({"asset_id": aid, "other_name": it.get("other", ""), "taken_at": taken,
                                 "predicted_status": (it.get("predicted") or {}).get("status", ""),
                                 "predicted_top1": top, "media_url": rel})
                ood_ids.add(aid)
                added["ood"] += 1
    with ref_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(ref_rows)
    with ood_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OOD_COLUMNS)
        w.writeheader()
        w.writerows(ood_rows)
    return added


if __name__ == "__main__":
    print(ingest(sys.argv[1:]))
