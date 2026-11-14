import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TAXONOMY_DIR = Path(__file__).parent
DEFAULT_TAXONOMY = "mvp21"
CATEGORIES = {"MINERAL", "ROCK"}


@dataclass(frozen=True)
class Taxon:
    taxon_id: str
    canonical_name: str
    category: str
    rank: str
    confusion_group: str


@lru_cache
def load_taxonomy(name: str = DEFAULT_TAXONOMY) -> dict[str, Taxon]:
    path = TAXONOMY_DIR / f"{name}.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        taxa = [Taxon(**row) for row in csv.DictReader(fh)]
    by_id = {t.taxon_id: t for t in taxa}
    if len(by_id) != len(taxa):
        raise ValueError(f"duplicate taxon_id in {path.name}")
    if len({t.canonical_name.lower() for t in taxa}) != len(taxa):
        raise ValueError(f"duplicate canonical_name in {path.name}")
    bad = [t.taxon_id for t in taxa if t.category not in CATEGORIES]
    if bad:
        raise ValueError(f"unknown category for {bad}")
    return by_id


def confusion_pairs(taxonomy: dict[str, Taxon]) -> list[tuple[str, str]]:
    """Taxon pairs sharing a confusion group; these seed the confusion-pair suite."""
    ids = sorted(taxonomy)
    return [
        (a, b)
        for i, a in enumerate(ids)
        for b in ids[i + 1 :]
        if taxonomy[a].confusion_group == taxonomy[b].confusion_group
    ]


def extra_taxon_ids() -> set[str]:
    """Taxa added after mvp21 (extra_minerals.csv, extra_rocks_ores.csv). The reference manifest accepts them."""
    ids: set[str] = set()
    for name in ("extra_minerals", "extra_rocks_ores"):
        path = TAXONOMY_DIR / f"{name}.csv"
        if path.exists():
            with path.open(newline="", encoding="utf-8") as fh:
                ids |= {r["taxon_id"] for r in csv.DictReader(fh)}
    return ids
