"""Collect candidate images per taxon into a review CSV. Re-running only appends new candidates
and never touches review decisions already made.

  python -m services.ingestion.harvest --sources smithsonian commons --per-taxon 40 \
      --out data_manifests/candidates/candidates.csv
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import httpx

from packages.taxonomy.loader import TAXONOMY_DIR, load_taxonomy
from services.ingestion.candidates import read_candidates, write_candidates
from dataclasses import replace

from services.ingestion.sources import commons, other_taxa_named, smithsonian

QUERIES = TAXONOMY_DIR / "harvest_queries.csv"


def load_queries() -> dict[str, dict[str, str]]:
    with QUERIES.open(newline="", encoding="utf-8") as fh:
        rows = {r["taxon_id"]: r for r in csv.DictReader(fh)}
    missing = set(load_taxonomy()) - set(rows)
    if missing:
        raise ValueError(f"harvest_queries.csv lacks {sorted(missing)}")
    return rows


def harvest(
    client: httpx.Client, sources: list[str], taxa: list[str] | None, per_taxon: int,
    out: str | Path, si_api_key: str = "DEMO_KEY", log=lambda *_: None,
) -> int:
    queries = load_queries()
    existing = [
        c if c.other_taxa_in_title else replace(c, other_taxa_in_title=other_taxa_named(c.title, c.taxon_id))
        for c in read_candidates(out)
    ]
    seen = {c.candidate_id for c in existing} | {c.media_url for c in existing}
    added = []
    exhausted: set[str] = set()
    for taxon_id in taxa or sorted(queries):
        q = queries[taxon_id]
        terms = q["title_terms"].split("|")
        for source in sources:
            if source in exhausted:
                continue
            try:
                if source == "commons":
                    found = commons.search(client, taxon_id, q["commons_query"], terms, per_taxon)
                elif source == "smithsonian":
                    found = []
                    for sub in q["smithsonian_query"].split("|"):
                        found += smithsonian.search(client, taxon_id, sub, terms, per_taxon, si_api_key)
                else:
                    raise ValueError(source)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    exhausted.add(source)
                    log(f"{source}: rate limited at {taxon_id}; skipping it for the rest of this run")
                else:
                    log(f"{source} {taxon_id}: {e}")
                continue
            except httpx.HTTPError as e:
                log(f"{source} {taxon_id}: {e}")
                continue
            new = [c for c in found if c.candidate_id not in seen and c.media_url not in seen]
            for c in new:
                seen |= {c.candidate_id, c.media_url}
            added += new
            log(f"{source:12} {taxon_id:16} found {len(found):3} new {len(new):3}")
    if added or existing:
        write_candidates(out, existing + added)
    return len(added)


def summarise(path: str | Path) -> str:
    rows = read_candidates(path)
    by: dict[str, dict[str, int]] = {}
    for r in rows:
        d = by.setdefault(r.taxon_id, {"total": 0, "allowed_train": 0, "allowed_reference_only": 0, "rejected": 0, "specimens": set()})
        d["total"] += 1
        d[r.proposed_usage] = d.get(r.proposed_usage, 0) + 1
        if r.proposed_usage != "rejected":
            d["specimens"].add(r.specimen_hint)
    lines = ["| taxon | candidates | proposed train | proposed reference-only | proposed rejected | usable specimens (hint) |",
             "|---|---|---|---|---|---|"]
    for t in sorted(load_taxonomy()):
        d = by.get(t, {"total": 0, "allowed_train": 0, "allowed_reference_only": 0, "rejected": 0, "specimens": set()})
        lines.append(f"| {t} | {d['total']} | {d['allowed_train']} | {d['allowed_reference_only']} | {d['rejected']} | {len(d['specimens'])} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="+", default=["smithsonian", "commons"])
    ap.add_argument("--taxa", nargs="*")
    ap.add_argument("--per-taxon", type=int, default=40)
    ap.add_argument("--out", default="data_manifests/candidates/candidates.csv")
    ap.add_argument("--summary", help="write a markdown summary here")
    a = ap.parse_args(argv)
    with httpx.Client(follow_redirects=True) as client:
        n = harvest(client, a.sources, a.taxa, a.per_taxon, a.out,
                    os.getenv("SI_API_KEY") or "DEMO_KEY", log=lambda m: print(m, file=sys.stderr))
    print(f"added {n} candidates", file=sys.stderr)
    if a.summary:
        Path(a.summary).write_text(summarise(a.out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
