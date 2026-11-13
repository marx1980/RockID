"""MineralImage5k (Fersman Mineralogical Museum photos) as a private-use reference and OOD source.

The images are not ours to redistribute, so they are never committed: the workflow downloads the Hugging Face
copy, embeds the photos with the app's model and keeps only vectors plus a label manifest without URLs.

  python -m services.ingestion.private_mineralimage5k inspect
  python -m services.ingestion.private_mineralimage5k extract OUT_DIR [--per-taxon N]
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = "Nech-C/mineralimage5K-98"
SOURCE = "MineralImage5k (Fersman Mineralogical Museum)"
LICENSE = "Dataset labelled MIT; museum photos, private use only"
# Dataset class name -> our taxon. Anything not listed is an "other mineral" and feeds the OOD pool.
TAXON = {
    "quartz": "min.quartz", "amethyst": "min.quartz", "citrine": "min.quartz", "rock crystal": "min.quartz",
    "smoky quartz": "min.quartz", "rose quartz": "min.quartz", "morion": "min.quartz",
    "calcite": "min.calcite", "pyrite": "min.pyrite", "fluorite": "min.fluorite", "gypsum": "min.gypsum",
    "selenite": "min.gypsum", "hematite": "min.hematite", "magnetite": "min.magnetite",
    "malachite": "min.malachite", "azurite": "min.azurite", "muscovite": "min.muscovite", "biotite": "min.biotite",
    "microcline": "min.k-feldspar", "orthoclase": "min.k-feldspar", "sanidine": "min.k-feldspar",
    "amazonite": "min.k-feldspar",
}
# Not minerals of the taxonomy and too close to a taxon to count as "other": left out of both pools.
AMBIGUOUS = {"chalcedony", "agate", "chrysoprase", "jasper", "chert", "flint", "opal", "marble", "limestone", "granite"}


def norm(name: str) -> str:
    return re.sub(r"[_\-]+", " ", str(name)).strip().lower()


def load():
    from datasets import load_dataset
    return load_dataset(REPO)


def class_names(ds) -> list[str]:
    feats = next(iter(ds.values())).features
    for key in ("name", "classes", "label"):
        if key in feats and hasattr(feats[key], "names"):
            return list(feats[key].names)
    raise SystemExit(f"no class-label feature in {list(feats)}")


def inspect() -> None:
    ds = load()
    print("splits", {k: len(v) for k, v in ds.items()})
    first = next(iter(ds.values()))
    print("features", first.features)
    row = first[0]
    print("row without image", {k: (v if k != "image" else f"<{type(v).__name__} {getattr(v, 'size', '')}>") for k, v in row.items()})
    names = class_names(ds)
    key = next(k for k in ("name", "classes", "label") if k in first.features and hasattr(first.features[k], "names"))
    counts = Counter()
    for split in ds.values():
        counts.update(split[key])
    print("classes", len(names))
    for i, n in sorted(((i, names[i]) for i in counts), key=lambda x: -counts[x[0]]):
        print(f"  {counts[i]:5d}  {n:28} -> {TAXON.get(norm(n), 'AMBIGUOUS' if norm(n) in AMBIGUOUS else 'other (OOD pool)')}")
    descs = [d for d in first["description"][:30] if d] if "description" in first.features else []
    print("sample descriptions", descs[:12])


def extract(out_dir: str, per_taxon: int = 120, per_other_class: int = 6) -> None:
    ds = load()
    names = class_names(ds)
    first = next(iter(ds.values()))
    key = next(k for k in ("name", "classes", "label") if k in first.features and hasattr(first.features[k], "names"))
    out = Path(out_dir)
    (out / "img").mkdir(parents=True, exist_ok=True)
    taken: dict[str, int] = defaultdict(int)
    rows = []
    for split_name, split in ds.items():
        for i, ex in enumerate(split):
            cls = norm(names[ex[key]])
            if cls in AMBIGUOUS:
                continue
            taxon = TAXON.get(cls)
            group = taxon or f"ood.{cls}"
            cap = per_taxon if taxon else per_other_class
            if taken[group] >= cap:
                continue
            taken[group] += 1
            aid = f"mi5k:{split_name}:{i}"
            fname = f"{split_name}_{i}.jpg"
            ex["image"].convert("RGB").save(out / "img" / fname, quality=92)
            rows.append({"asset_id": aid, "taxon_id": group, "dataset_class": cls, "specimen_id": aid, "form": "natural",
                         "source_name": SOURCE, "license": LICENSE, "media_url": str(out / "img" / fname)})
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(dict(sorted(taken.items())), indent=0))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "extract"])
    ap.add_argument("out", nargs="?")
    ap.add_argument("--per-taxon", type=int, default=120)
    a = ap.parse_args()
    inspect() if a.cmd == "inspect" else extract(a.out, a.per_taxon)
