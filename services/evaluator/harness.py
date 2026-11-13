"""Blind evaluation harness.

Order is enforced, not just documented:
  1. the store hands out image bytes only,
  2. the identifier's answer is frozen in an append-only ledger (with its sha256),
  3. only then will the store reveal the hidden truth for that case.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from services.evaluator.metrics import UNKNOWN, CaseResult

IdentifyFn = Callable[[bytes], dict]


@dataclass(frozen=True)
class RevealedTruth:
    ground_truth_id: str  # taxon_id, or UNKNOWN for OOD cases
    accepted_labels: tuple[str, ...] = ()


class NotFrozenError(RuntimeError):
    pass


class PredictionLedger:
    """Append-only JSONL. A case can be frozen once; frozen records are never rewritten."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._frozen: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                self._frozen[rec["case_id"]] = rec

    def is_frozen(self, case_id: str) -> bool:
        return case_id in self._frozen

    def freeze(self, case_id: str, prediction: dict) -> dict:
        if self.is_frozen(case_id):
            raise ValueError(f"case {case_id} already frozen")
        payload = json.dumps(prediction, sort_keys=True, separators=(",", ":"))
        rec = {
            "case_id": case_id,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "prediction_sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "prediction": prediction,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        self._frozen[case_id] = rec
        return rec

    def get(self, case_id: str) -> dict:
        return self._frozen[case_id]


class ChallengeStore(Protocol):
    def list_case_ids(self, suite: str) -> list[str]: ...
    def image_bytes(self, case_id: str) -> bytes: ...
    def reveal(self, case_id: str, ledger: PredictionLedger) -> RevealedTruth: ...


class InMemoryChallengeStore:
    """Reference implementation of the reveal-after-freeze rule (used by tests and dry runs)."""

    def __init__(self, cases: dict[str, tuple[str, bytes, RevealedTruth]]):
        self._cases = cases  # case_id -> (suite, image bytes, truth)

    def list_case_ids(self, suite: str) -> list[str]:
        return sorted(cid for cid, (s, _, _) in self._cases.items() if s == suite)

    def image_bytes(self, case_id: str) -> bytes:
        return self._cases[case_id][1]

    def reveal(self, case_id: str, ledger: PredictionLedger) -> RevealedTruth:
        if not ledger.is_frozen(case_id):
            raise NotFrozenError(f"prediction for {case_id} is not frozen")
        return self._cases[case_id][2]


def http_identifier(base_url: str, timeout: float = 60.0) -> IdentifyFn:
    import httpx

    def identify(raw: bytes) -> dict:
        # Bytes only: no filename, no case id, no metadata that could carry the label.
        resp = httpx.post(
            f"{base_url.rstrip('/')}/v1/identify",
            files={"image": ("image", raw, "application/octet-stream")},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()

    return identify


def to_case_result(prediction: dict, truth: RevealedTruth) -> CaseResult:
    abstained = prediction.get("status") != "identified"
    cands = prediction.get("top_candidates") or []
    return CaseResult(
        truth=truth.ground_truth_id or UNKNOWN,
        ranked=[c["taxon_id"] for c in cands],
        abstained=abstained,
        confidence=cands[0]["probability"] if cands else None,
        accepted=frozenset(truth.accepted_labels),
    )


def run_suite(store: ChallengeStore, suite: str, identify: IdentifyFn, ledger: PredictionLedger) -> list[CaseResult]:
    case_ids = store.list_case_ids(suite)
    for cid in case_ids:  # phase 1: predict and freeze everything
        if not ledger.is_frozen(cid):
            ledger.freeze(cid, identify(store.image_bytes(cid)))
    # phase 2: reveal and score
    return [to_case_result(ledger.get(cid)["prediction"], store.reveal(cid, ledger)) for cid in case_ids]
