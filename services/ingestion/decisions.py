"""Reviewer decisions, kept apart from the harvested candidates so a harvest re-run can never
overwrite them. File format: {"<candidate_id>": "approve_train" | "approve_reference" | "reject"}."""
import json
from dataclasses import replace
from pathlib import Path

from services.ingestion.candidates import REVIEW_DECISIONS, Candidate
from services.ingestion.licence import permits

DECISION_TO_USAGE = {"approve_train": "allowed_train", "approve_reference": "allowed_reference_only"}
VALID = REVIEW_DECISIONS - {""}


def load_decisions(path: str | Path | None) -> dict[str, str]:
    if not path or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_forms(path: str | Path | None) -> dict[str, str]:
    """Form of each non-natural candidate: {"<candidate_id>": "tumbled" | "polished"}. Absent means natural."""
    if not path or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_forms(path: str | Path, forms: dict[str, str]) -> None:
    Path(path).write_text(json.dumps(dict(sorted(forms.items())), indent=0, ensure_ascii=False) + "\n", encoding="utf-8")


def save_decisions(path: str | Path, decisions: dict[str, str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(dict(sorted(decisions.items())), indent=0, ensure_ascii=False) + "\n", encoding="utf-8")


def apply_decisions(cands: list[Candidate], decisions: dict[str, str]) -> list[Candidate]:
    return [replace(c, review_decision=decisions[c.candidate_id]) if c.candidate_id in decisions else c for c in cands]


def validate_decisions(cands: list[Candidate], decisions: dict[str, str]) -> list[str]:
    by_id = {c.candidate_id: c for c in cands}
    problems = []
    for cid, decision in decisions.items():
        if cid not in by_id:
            problems.append(f"{cid}: unknown candidate")
        elif decision not in VALID:
            problems.append(f"{cid}: invalid decision {decision!r}")
        elif decision in DECISION_TO_USAGE and not permits(by_id[cid].license, DECISION_TO_USAGE[decision]):
            problems.append(f"{cid}: licence {by_id[cid].license!r} does not permit {DECISION_TO_USAGE[decision]}")
    return problems


if __name__ == "__main__":
    import sys

    from services.ingestion.candidates import read_candidates

    cands = read_candidates(sys.argv[1])
    issues = validate_decisions(cands, load_decisions(sys.argv[2]))
    print("\n".join(issues) or "ok")
    sys.exit(1 if issues else 0)
