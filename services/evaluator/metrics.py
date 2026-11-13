"""Benchmark metrics (docs/evaluation.md).

Conventions:
- `truth == UNKNOWN` marks an out-of-taxonomy (OOD) case; the right answer is to abstain.
- Abstentions count as misses in top-k accuracy, so abstaining never inflates accuracy;
  `coverage` and `selective_accuracy` show the other side of the trade-off.
"""
from dataclasses import dataclass, field

UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CaseResult:
    truth: str
    ranked: list[str]
    abstained: bool = False
    confidence: float | None = None  # model probability of ranked[0]
    accepted: frozenset[str] = field(default_factory=frozenset)  # extra acceptable labels

    @property
    def is_ood(self) -> bool:
        return self.truth == UNKNOWN

    def correct_labels(self) -> frozenset[str]:
        return frozenset({self.truth}) | self.accepted

    def hit_at(self, k: int) -> bool:
        return not self.abstained and bool(self.correct_labels() & set(self.ranked[:k]))

    @property
    def top1(self) -> str | None:
        return None if self.abstained or not self.ranked else self.ranked[0]


def _in_taxonomy(rows: list[CaseResult]) -> list[CaseResult]:
    return [r for r in rows if not r.is_ood]


def top_k_accuracy(rows: list[CaseResult], k: int) -> float:
    rows = _in_taxonomy(rows)
    return sum(r.hit_at(k) for r in rows) / len(rows) if rows else 0.0


def ranked_accuracy(rows: list[CaseResult], k: int) -> float:
    """Top-k of the ranked list, ignoring abstention: is the right answer on the shortlist?"""
    rows = _in_taxonomy(rows)
    return sum(bool(r.correct_labels() & set(r.ranked[:k])) for r in rows) / len(rows) if rows else 0.0


def category_accuracy(rows: list[CaseResult]) -> float:
    """Mineral vs rock (taxon_id prefix) of the first-ranked answer."""
    rows = [r for r in _in_taxonomy(rows) if r.ranked]
    return sum(r.ranked[0].split(".")[0] == r.truth.split(".")[0] for r in rows) / len(rows) if rows else 0.0


def coverage(rows: list[CaseResult]) -> float:
    rows = _in_taxonomy(rows)
    return sum(not r.abstained for r in rows) / len(rows) if rows else 0.0


def selective_accuracy(rows: list[CaseResult]) -> float:
    answered = [r for r in _in_taxonomy(rows) if not r.abstained]
    return sum(r.hit_at(1) for r in answered) / len(answered) if answered else 0.0


def confident_error_rate(rows: list[CaseResult], min_confidence: float | None = None) -> float:
    """Share of answered cases (optionally only those at/above `min_confidence`) whose top-1 is wrong.
    An answered OOD case is always an error."""
    answered = [r for r in rows if not r.abstained]
    if min_confidence is not None:
        answered = [r for r in answered if (r.confidence or 0.0) >= min_confidence]
    if not answered:
        return 0.0
    return sum(r.is_ood or not r.hit_at(1) for r in answered) / len(answered)


def unknown_false_accept_rate(rows: list[CaseResult]) -> float:
    ood = [r for r in rows if r.is_ood]
    return sum(not r.abstained for r in ood) / len(ood) if ood else 0.0


def per_class_recall(rows: list[CaseResult]) -> dict[str, float]:
    out: dict[str, list[bool]] = {}
    for r in _in_taxonomy(rows):
        out.setdefault(r.truth, []).append(r.hit_at(1))
    return {c: sum(v) / len(v) for c, v in sorted(out.items())}


def macro_f1(rows: list[CaseResult]) -> float:
    rows = _in_taxonomy(rows)
    classes = sorted({r.truth for r in rows})
    if not classes:
        return 0.0
    f1s = []
    for c in classes:
        tp = sum(r.truth == c and r.hit_at(1) for r in rows)
        fp = sum(r.top1 == c and not r.hit_at(1) for r in rows)
        fn = sum(r.truth == c and not r.hit_at(1) for r in rows)
        p = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * p * rec / (p + rec) if p + rec else 0.0)
    return sum(f1s) / len(f1s)


def expected_calibration_error(rows: list[CaseResult], bins: int = 10) -> float:
    scored = [r for r in rows if not r.abstained and r.confidence is not None]
    if not scored:
        return 0.0
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [r for r in scored if lo <= r.confidence < hi or (b == bins - 1 and r.confidence == 1.0)]
        if bucket:
            acc = sum((not r.is_ood) and r.hit_at(1) for r in bucket) / len(bucket)
            conf = sum(r.confidence for r in bucket) / len(bucket)
            total += len(bucket) / len(scored) * abs(acc - conf)
    return total


def report(rows: list[CaseResult]) -> dict:
    return {
        "cases": len(rows),
        "ood_cases": sum(r.is_ood for r in rows),
        "top1": top_k_accuracy(rows, 1),
        "top3": top_k_accuracy(rows, 3),
        "ranked_top1": ranked_accuracy(rows, 1),
        "ranked_top3": ranked_accuracy(rows, 3),
        "category_accuracy": category_accuracy(rows),
        "macro_f1": macro_f1(rows),
        "per_class_recall": per_class_recall(rows),
        "coverage": coverage(rows),
        "selective_accuracy": selective_accuracy(rows),
        "confident_error_rate": confident_error_rate(rows),
        "unknown_false_accept_rate": unknown_false_accept_rate(rows),
        "ece": expected_calibration_error(rows),
    }
