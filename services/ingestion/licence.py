"""Licence -> proposed usage decision. The policy lives in licence_policy.csv (first match wins).
This only *proposes*; a human review decision is always required before promotion."""
import csv
import re
from functools import lru_cache
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("licence_policy.csv")
RANK = {"rejected": 0, "pending": 0, "allowed_reference_only": 1, "allowed_train": 2}


@lru_cache
def _policy() -> list[tuple[re.Pattern, str, str]]:
    with POLICY_PATH.open(newline="", encoding="utf-8") as fh:
        return [(re.compile(r["pattern"]), r["proposed_usage"], r["reason"]) for r in csv.DictReader(fh)]


def normalise(licence: str) -> str:
    return re.sub(r"\s+", " ", (licence or "").strip().lower())


def propose_usage(licence: str) -> tuple[str, str]:
    norm = normalise(licence)
    for pattern, usage, reason in _policy():
        if pattern.search(norm):
            return usage, reason
    return "rejected", "no policy match"


def permits(licence: str, requested_usage: str) -> bool:
    """True if the licence policy allows at least `requested_usage`."""
    return RANK[propose_usage(licence)[0]] >= RANK[requested_usage] > 0
