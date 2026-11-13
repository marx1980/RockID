"""Build app/data.json from the taxonomy data files.  python -m services.app.build_data app/data.json"""
import csv
import json
import sys
from pathlib import Path

from packages.taxonomy.loader import TAXONOMY_DIR, load_taxonomy


def build() -> dict:
    tax = load_taxonomy()
    with (TAXONOMY_DIR / "properties.csv").open(newline="", encoding="utf-8") as fh:
        props = {r["taxon_id"]: r for r in csv.DictReader(fh)}
    with (TAXONOMY_DIR / "followups.csv").open(newline="", encoding="utf-8") as fh:
        groups = {}
        for r in csv.DictReader(fh):
            answers = [a.split("=", 1) for a in r["answers"].split("|")]
            groups[r["confusion_group"]] = {"q": r["test"], "a": [{"label": l, "taxon": t} for l, t in answers]}
    taxa = {}
    with (TAXONOMY_DIR / "extra_minerals.csv").open(newline="", encoding="utf-8") as fh:
        extra = list(csv.DictReader(fh))
    for r in extra:
        props[r["taxon_id"]] = r
        tax = {**tax, r["taxon_id"]: type("T", (), {"canonical_name": r["canonical_name"], "category": r["category"],
                                                    "confusion_group": r["confusion_group"]})()}
    for tid, t in tax.items():
        p = props[tid]
        taxa[tid] = {
            "name": t.canonical_name, "category": t.category.title(), "group": t.confusion_group,
            "makeup": p["formula_or_makeup"], "hardness": p["hardness"], "streak": p["streak"],
            "luster": p["luster"], "class": p["class"], "features": p["features"].split("|"),
        }
    return {"taxonomy_version": "mvp21-v1+extra78", "taxa": taxa, "followups": groups}


def check(data: dict) -> list[str]:
    problems = []
    for g, f in data["followups"].items():
        for a in f["a"]:
            if a["taxon"] not in data["taxa"]:
                problems.append(f"{g}: unknown taxon {a['taxon']}")
            elif data["taxa"][a["taxon"]]["group"] != g:
                problems.append(f"{g}: {a['taxon']} is not in this group")
    return problems


if __name__ == "__main__":
    d = build()
    assert not check(d), check(d)
    Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[1]).write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
