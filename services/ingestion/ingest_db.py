"""Load a validated reference manifest into the reference Postgres (taxa, specimens, assets).
Idempotent; an invalid manifest changes nothing.

  REFERENCE_DATABASE_URL=postgresql://... python -m services.ingestion.ingest_db data_manifests/reference/reference.csv
"""
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from packages.taxonomy.loader import load_taxonomy
from services.ingestion.manifest import validate_file

TAXONOMY_VERSION = os.getenv("TAXONOMY_VERSION", "mvp21-v1")


class IngestError(RuntimeError):
    pass


@dataclass
class IngestResult:
    taxa: int = 0
    specimens: int = 0
    assets_inserted: int = 0
    assets_existing: int = 0


def ingest(conn, manifest: str | Path, taxonomy_name: str = "mvp21") -> IngestResult:
    problems = validate_file(manifest, taxonomy_name)
    if problems:
        raise IngestError(f"{len(problems)} manifest problem(s): " + "; ".join(problems[:5]))
    with Path(manifest).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    res = IngestResult()
    with conn.transaction():
        cur = conn.cursor()
        for t in load_taxonomy(taxonomy_name).values():
            cur.execute(
                """INSERT INTO taxa (taxon_id, canonical_name, category, rank, confusion_group, taxonomy_version)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (taxon_id) DO UPDATE SET canonical_name=EXCLUDED.canonical_name,
                     category=EXCLUDED.category, rank=EXCLUDED.rank,
                     confusion_group=EXCLUDED.confusion_group, taxonomy_version=EXCLUDED.taxonomy_version""",
                (t.taxon_id, t.canonical_name, t.category, t.rank, t.confusion_group, TAXONOMY_VERSION),
            )
            res.taxa += 1
        specimens_seen: set[str] = set()
        for r in rows:
            if r["specimen_id"] not in specimens_seen:
                cur.execute(
                    "SELECT taxon_id FROM specimens WHERE specimen_id=%s", (r["specimen_id"],))
                existing = cur.fetchone()
                if existing and existing[0] != r["taxon_id"]:
                    raise IngestError(f"specimen {r['specimen_id']} already stored under {existing[0]}")
                cur.execute(
                    "INSERT INTO specimens (specimen_id, taxon_id, source_name) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (r["specimen_id"], r["taxon_id"], r["source_name"]),
                )
                specimens_seen.add(r["specimen_id"])
                res.specimens += 1
            cur.execute(
                """INSERT INTO assets (asset_id, specimen_id, source_name, source_url, media_url, author, license,
                                       retrieval_date, usage_decision, sha256, phash)
                   VALUES (%(asset_id)s,%(specimen_id)s,%(source_name)s,%(source_url)s,%(media_url)s,%(author)s,
                           %(license)s,%(retrieval_date)s,%(usage_decision)s,%(sha256)s,%(phash)s)
                   ON CONFLICT (asset_id) DO NOTHING""",
                r,
            )
            if cur.rowcount:
                res.assets_inserted += 1
            else:
                res.assets_existing += 1
    return res


def main(argv=None) -> int:
    import psycopg

    manifest = (argv or sys.argv[1:])[0]
    with psycopg.connect(os.environ["REFERENCE_DATABASE_URL"]) as conn:
        print(ingest(conn, manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
