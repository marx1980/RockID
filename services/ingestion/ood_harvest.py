"""Candidates for an out-of-distribution (OOD) set: things the identifier must NOT name as one of its taxa
(other minerals, other rocks, man-made material, other natural objects). Collected from Commons categories
listed in packages/taxonomy/ood_categories.csv into a separate candidates file; labels are `ood.<group>`.
OOD photos never enter the reference set. They go to the vault as cases with truth UNKNOWN.

  python -m services.ingestion.ood_harvest --out data_manifests/candidates/ood_candidates.csv
"""
import argparse
import csv
import sys
from pathlib import Path

import httpx

from packages.taxonomy.loader import TAXONOMY_DIR
from services.ingestion.candidates import read_candidates, write_candidates
from services.ingestion.sources import commons_categories

OOD_CATEGORIES = TAXONOMY_DIR / "ood_categories.csv"


def load_groups() -> dict[str, list[str]]:
    with OOD_CATEGORIES.open(newline="", encoding="utf-8") as fh:
        return {f"ood.{r['group']}": [x for x in r["categories"].split("|") if x] for r in csv.DictReader(fh)}


def harvest(client: httpx.Client, out: str | Path, per_category: int = 60, log=lambda *_: None) -> int:
    existing = read_candidates(out)
    seen = {c.candidate_id for c in existing} | {c.media_url for c in existing}
    added = []
    for group, categories in load_groups().items():
        for category in categories:
            try:
                found = commons_categories.category_files(client, category, group, [], per_category)
            except httpx.HTTPError as e:
                log(f"{group} {category}: {e}")
                continue
            new = []
            for c in found:
                if c.candidate_id in seen or c.media_url in seen:
                    continue
                seen |= {c.candidate_id, c.media_url}
                new.append(c)
            added += new
            log(f"{group:18} {category:45} found {len(found):3} new {len(new):3}")
    write_candidates(out, existing + added)
    return len(added)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data_manifests/candidates/ood_candidates.csv")
    ap.add_argument("--per-category", type=int, default=60)
    a = ap.parse_args(argv)
    with httpx.Client(follow_redirects=True) as client:
        n = harvest(client, a.out, a.per_category, log=lambda m: print(m, file=sys.stderr))
    print(f"added {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
