"""Candidate images awaiting human review. Not reference data until promoted."""
import csv
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

REVIEW_DECISIONS = {"", "approve_train", "approve_reference", "reject"}


@dataclass(frozen=True)
class Candidate:
    candidate_id: str  # source:record:media, stable across runs
    taxon_id: str
    source_name: str
    source_record_id: str
    title: str
    source_url: str  # human-readable record page
    media_url: str  # image actually downloaded (resized where the source supports it)
    author: str
    license: str
    license_url: str
    specimen_hint: str
    specimen_hint_confidence: str  # high = source gives a specimen/catalogue id; low = guessed
    taxon_in_title: bool
    other_taxa_in_title: str  # other MVP taxa named in the title, '|'-separated; label may be ambiguous
    proposed_usage: str
    policy_reason: str
    retrieved_at: str
    review_decision: str = ""
    reviewer_note: str = ""

    def with_review(self, decision: str, note: str = "") -> "Candidate":
        if decision not in REVIEW_DECISIONS:
            raise ValueError(decision)
        return replace(self, review_decision=decision, reviewer_note=note)


CANDIDATE_COLUMNS = [f.name for f in fields(Candidate)]


def _from_row(row: dict[str, str]) -> Candidate:
    data = {k: row.get(k, "") for k in CANDIDATE_COLUMNS}
    data["taxon_in_title"] = str(data["taxon_in_title"]).lower() == "true"
    if data["review_decision"] not in REVIEW_DECISIONS:
        raise ValueError(f"{data['candidate_id']}: invalid review_decision {data['review_decision']!r}")
    return Candidate(**data)


def read_candidates(path: str | Path) -> list[Candidate]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [_from_row(r) for r in csv.DictReader(fh)]


def write_candidates(path: str | Path, rows: list[Candidate]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CANDIDATE_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))
