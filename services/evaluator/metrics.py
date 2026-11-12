from dataclasses import dataclass

@dataclass(frozen=True)
class CaseResult:
    truth: str
    ranked: list[str]
    abstained: bool = False

def top_k_accuracy(rows: list[CaseResult], k: int) -> float:
    if not rows: return 0.0
    return sum(r.truth in r.ranked[:k] for r in rows) / len(rows)

def confident_error_rate(rows: list[CaseResult]) -> float:
    non_abstained = [r for r in rows if not r.abstained]
    if not non_abstained: return 0.0
    return sum((not r.ranked) or r.ranked[0] != r.truth for r in non_abstained) / len(non_abstained)
