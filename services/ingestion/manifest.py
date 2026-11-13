"""Reference manifest validation. A row that fails here never reaches the reference DB."""
import csv
import re
from dataclasses import dataclass
from pathlib import Path

from packages.taxonomy.loader import load_taxonomy

REFERENCE_COLUMNS = [
    "asset_id", "taxon_id", "specimen_id", "source_name", "source_url", "author",
    "license", "retrieval_date", "usage_decision", "sha256", "phash", "media_url", "form",
]
# What the stone looks like in the photo: raw (natural), tumbled (rounded by machine or water) or
# polished (polished or sawn slab, cabochon, sphere). Blank means natural.
FORMS = ("natural", "tumbled", "polished")
USAGE_DECISIONS = {"allowed_train", "allowed_reference_only", "rejected", "pending"}
INGESTIBLE = {"allowed_train", "allowed_reference_only"}
# Anything that smells like hidden challenge truth must never appear in a reference manifest.
FORBIDDEN_COLUMN_PATTERNS = ("ground_truth", "accepted_label", "challenge", "difficulty")

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PHASH = re.compile(r"^[0-9a-f]{16}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class RowError:
    line: int
    asset_id: str
    problem: str


def check_header(header: list[str]) -> list[str]:
    problems = [f"missing column {c}" for c in REFERENCE_COLUMNS if c not in header]
    for col in header:
        if any(p in col.lower() for p in FORBIDDEN_COLUMN_PATTERNS):
            problems.append(f"forbidden column {col}")
    return problems


def validate_rows(rows: list[dict[str, str]], taxonomy_name: str = "mvp21") -> list[RowError]:
    taxa = load_taxonomy(taxonomy_name)
    errors: list[RowError] = []
    seen_assets: set[str] = set()
    seen_sha: set[str] = set()
    specimen_taxon: dict[str, str] = {}
    for i, row in enumerate(rows, start=2):  # line 1 is the header
        aid = row.get("asset_id", "")

        def err(msg: str) -> None:
            errors.append(RowError(i, aid, msg))

        if not aid:
            err("empty asset_id")
        elif aid in seen_assets:
            err("duplicate asset_id")
        seen_assets.add(aid)
        if row.get("taxon_id") not in taxa:
            err(f"unknown taxon_id {row.get('taxon_id')!r}")
        if not row.get("specimen_id"):
            err("empty specimen_id (needed for specimen-level leakage checks)")
        else:
            first = specimen_taxon.setdefault(row["specimen_id"], row.get("taxon_id", ""))
            if first != row.get("taxon_id", ""):
                err(f"specimen {row['specimen_id']} appears under two taxa ({first}, {row.get('taxon_id')})")
        decision = row.get("usage_decision")
        if decision not in USAGE_DECISIONS:
            err(f"invalid usage_decision {decision!r}")
        elif decision not in INGESTIBLE:
            err(f"usage_decision {decision} is not ingestible")
        if decision in INGESTIBLE and not row.get("license"):
            err("ingestible row has no license")
        if not row.get("source_url"):
            err("empty source_url")
        if not str(row.get("media_url", "")).startswith("https://"):
            err("media_url must be an https URL")
        if not _DATE.match(row.get("retrieval_date", "")):
            err("retrieval_date must be YYYY-MM-DD")
        sha = row.get("sha256", "")
        if not _SHA256.match(sha):
            err("sha256 must be 64 lowercase hex chars")
        elif sha in seen_sha:
            err("duplicate sha256 (exact duplicate image)")
        seen_sha.add(sha)
        if not _PHASH.match(row.get("phash", "")):
            err("phash must be 16 lowercase hex chars")
        if (row.get("form") or "natural") not in FORMS:
            err(f"invalid form {row.get('form')!r}")
    return errors


def validate_file(path: str | Path, taxonomy_name: str = "mvp21") -> list[str]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        problems = check_header(reader.fieldnames or [])
        rows = list(reader)
    problems += [f"line {e.line} ({e.asset_id}): {e.problem}" for e in validate_rows(rows, taxonomy_name)]
    return problems


if __name__ == "__main__":
    import sys

    issues = [p for f in sys.argv[1:] for p in (f"{f}: {x}" for x in validate_file(f))]
    print("\n".join(issues) or "ok")
    sys.exit(1 if issues else 0)
