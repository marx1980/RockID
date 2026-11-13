"""Inventory of the Geological Survey of Japan specimen database as served by Cultural Japan IIIF manifests
(api.cultural.jp/iiif/musee_gsj-<n>/manifest). Reads manifests only (no images): id, English label, description,
licence, place, image URL. Writes a CSV and prints counts by licence and by rock/mineral name.

    python -m services.ingestion.gsj_inventory out.csv [--max-id 7000]"""
import csv
import re
import sys
import time
from collections import Counter

import httpx

API = "https://api.cultural.jp/iiif/musee_gsj-{n}/manifest"
UA = "RockID-inventory/0.1 (https://github.com/marx1980/RockID)"
NAMES = ["granite", "basalt", "gabbro", "rhyolite", "andesite", "diorite", "dacite", "tuff", "breccia", "sandstone", "limestone",
         "shale", "mudstone", "conglomerate", "chert", "marble", "slate", "schist", "gneiss", "quartzite", "phyllite", "hornfels",
         "serpentinite", "peridotite", "obsidian", "pumice", "quartz", "calcite", "feldspar", "mica", "gypsum", "halite",
         "pyrite", "magnetite", "hematite", "fluorite", "malachite", "azurite"]


def lang(values, code):
    for v in values or []:
        if isinstance(v, dict) and v.get("@language") == code:
            return v.get("@value", "")
    return ""


def parse(m: dict) -> dict:
    canvas = m["sequences"][0]["canvases"][0]
    img = canvas["images"][0]["resource"]["@id"]
    place = ""
    for md in m.get("metadata", []):
        if lang(md.get("label"), "en") == "Place":
            place = lang(md.get("value"), "en")
    return {"label": lang(m.get("label"), "en"), "description": " | ".join(m.get("description") or []),
            "licence": m.get("license", ""), "place": place, "image_url": img}


def main(out: str, max_id: int) -> None:
    rows, misses = [], 0
    with httpx.Client(headers={"User-Agent": UA}, timeout=40) as c:
        for n in range(1, max_id + 1):
            try:
                r = c.get(API.format(n=n))
            except httpx.HTTPError as e:
                print(f"{n}: {e}", file=sys.stderr)
                continue
            if r.status_code == 404:
                misses += 1
                if misses > 400 and n > 2000:
                    break
                continue
            misses = 0
            try:
                rows.append({"id": f"musee_gsj-{n}", **parse(r.json())})
            except (KeyError, IndexError, ValueError) as e:
                print(f"{n}: parse {e}", file=sys.stderr)
            time.sleep(0.05)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "label", "description", "licence", "place", "image_url"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} items; last id {rows[-1]['id'] if rows else '-'}")
    print("licences:", Counter(r["licence"] or "none" for r in rows).most_common())
    def kind(r):
        d = r["description"] + " " + r["label"]
        return "rock" if re.search(r"\bRock\b|岩石", d) else "mineral" if re.search(r"Mineral|鉱物|Oxides|Sulfides|Silicates|Carbonates|Native", d) else "fossil/other"
    print("kinds:", Counter(kind(r) for r in rows).most_common())
    open_ = [r for r in rows if "creativecommons.org/licenses/by/" in r["licence"] or "publicdomain" in r["licence"] or "zero" in r["licence"]]
    print("open-licence items:", len(open_), Counter(kind(r) for r in open_).most_common())
    names = Counter()
    for r in open_:
        for nme in NAMES:
            if re.search(rf"\b{nme}", r["label"], re.I):
                names[nme] += 1
    print("open-licence items by name:", names.most_common())


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == "--max-id" else 7000)
