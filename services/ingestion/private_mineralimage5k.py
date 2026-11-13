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


# Dataset spellings -> mineral names used as taxa when every species becomes a class (extract-all).
RENAME = {"cancrinit": "cancrinite", "scheelit": "scheelite", "elbait": "elbaite", "vesuvian": "vesuvianite",
          "labrador": "labradorite", "nephritis": "nephrite", "cobaltin": "cobaltite", "analcim": "analcime",
          "antimonite": "stibnite", "fluorapatite": "apatite", "lapis lazuli": "lapis-lazuli"}
SKIP_ALL = {"credit"}  # unresolved dataset label
# Description words that mean jewellery or cut stones: left out (faceted gems stay rejected).
BAD_DESC = re.compile(r"facet|\bring\b|necklace|bracelet|earring|pendant|\bbeads?\b|carv|figur|sculpt|statue|insect", re.I)


def form_of(desc: str) -> str:
    d = (desc or "").lower()
    if "tumbled" in d:
        return "tumbled"
    if "polish" in d or "cabochon" in d or "sphere" in d or "slab" in d:
        return "polished"
    return "natural"


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


def extract_all(out_dir: str, per_class: int = 100) -> None:
    """Every dataset species outside our 21 taxa becomes its own taxon (min.<name>), capped per class, with a
    form read from the photo description. Writes manifest.csv (local paths) and labels.csv (no paths)."""
    ds = load()
    names = class_names(ds)
    first = next(iter(ds.values()))
    key = next(k for k in ("name", "classes", "label") if k in first.features and hasattr(first.features[k], "names"))
    out = Path(out_dir)
    (out / "img").mkdir(parents=True, exist_ok=True)
    taken: dict[str, int] = defaultdict(int)
    skipped: Counter = Counter()
    rows = []
    for split_name, split in ds.items():
        for i, ex in enumerate(split):
            cls = norm(names[ex[key]])
            if cls in AMBIGUOUS or cls in TAXON or cls in SKIP_ALL:
                continue
            desc = ex.get("description") or ""
            if BAD_DESC.search(desc):
                skipped["jewellery_or_cut"] += 1
                continue
            cls = RENAME.get(cls, cls)
            taxon = "min." + cls.replace(" ", "-")
            if taken[taxon] >= per_class:
                continue
            taken[taxon] += 1
            aid = f"mi5k:{split_name}:{i}"
            fname = f"{split_name}_{i}.jpg"
            ex["image"].convert("RGB").save(out / "img" / fname, quality=92)
            rows.append({"asset_id": aid, "taxon_id": taxon, "specimen_id": aid, "form": form_of(desc),
                         "source_name": SOURCE, "license": LICENSE, "media_url": str(out / "img" / fname)})
    with (out / "all_inputs.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with (out / "all_labels.csv").open("w", newline="", encoding="utf-8") as fh:
        cols = [c for c in rows[0] if c != "media_url"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"classes": len(taken), "photos": len(rows), "skipped": dict(skipped),
                      "forms": dict(Counter(r["form"] for r in rows)), "per_class": dict(sorted(taken.items()))}))


def split(out_dir: str) -> None:
    """From extract's manifest.csv: reference rows, and OOD rows split by whole class (species) into
    calibration and test halves, so no mineral species is on both sides. Writes ref_inputs.csv,
    ood_cal_inputs.csv, ood_test_inputs.csv (with local file paths, for embedding) and the label files
    ref_labels.csv, ood_cal.csv, ood_test.csv (no paths) that are safe to commit."""
    out = Path(out_dir)
    rows = list(csv.DictReader((out / "manifest.csv").open(newline="", encoding="utf-8")))
    ref = [r for r in rows if not r["taxon_id"].startswith("ood.")]
    ood = [r for r in rows if r["taxon_id"].startswith("ood.")]
    classes = sorted({r["dataset_class"] for r in ood})
    side = {c: ("cal" if i % 2 == 0 else "test") for i, c in enumerate(classes)}

    def write(name, items, cols):
        with (out / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(items)

    ref_cols = ["asset_id", "taxon_id", "specimen_id", "form", "source_name", "license"]
    write("ref_inputs.csv", ref, ref_cols + ["media_url"])
    write("ref_labels.csv", ref, ref_cols)
    for tag in ("cal", "test"):
        items = [{**r, "case_id": r["asset_id"], "ground_truth_id": "UNKNOWN", "ood_group": "ood.other_mineral"}
                 for r in ood if side[r["dataset_class"]] == tag]
        write(f"ood_{tag}_inputs.csv", items, ["case_id", "media_url"])
        write(f"ood_{tag}.csv", items, ["case_id", "ground_truth_id", "ood_group", "dataset_class", "source_name", "license"])
    print(json.dumps({"reference": len(ref), "ood_cal": sum(side[r["dataset_class"]] == "cal" for r in ood),
                      "ood_test": sum(side[r["dataset_class"]] == "test" for r in ood), "ood_classes": len(classes)}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "extract", "split", "extract-all"])
    ap.add_argument("out", nargs="?")
    ap.add_argument("--per-taxon", type=int, default=120)
    a = ap.parse_args()
    if a.cmd == "inspect":
        inspect()
    elif a.cmd == "extract":
        extract(a.out, a.per_taxon)
    elif a.cmd == "extract-all":
        extract_all(a.out, a.per_taxon)
    else:
        split(a.out)
