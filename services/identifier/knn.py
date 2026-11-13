"""Reference vector search with specimen-balanced taxon aggregation and abstention.

Why specimen-balanced: a reference set often has 40 photos of one showy specimen and
2 of another. Raw k-NN voting would let that one specimen decide. Here each specimen
votes once (its best-matching photo), and each taxon counts at most `max_specimens_per_taxon`
specimens.

All thresholds are placeholders; they must be calibrated on held-out challenge data.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ReferenceItem:
    asset_id: str
    specimen_id: str
    taxon_id: str


@dataclass(frozen=True)
class Neighbor:
    item: ReferenceItem
    similarity: float


@dataclass(frozen=True)
class TaxonScore:
    taxon_id: str
    probability: float
    best_similarity: float
    supporting_specimens: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    status: str  # identified | uncertain | unknown
    candidates: list[TaxonScore]
    reason: str | None = None


def _normalize(m: np.ndarray) -> np.ndarray:
    m = np.atleast_2d(np.asarray(m, dtype=np.float32))
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(n == 0, 1, n)


class ReferenceIndex:
    """Exact cosine search in memory. The pgvector table (infra/db/reference) is the
    persistent equivalent; this class is the contract both must satisfy."""

    def __init__(self, items: list[ReferenceItem], vectors: np.ndarray):
        if len(items) != len(vectors):
            raise ValueError("items and vectors differ in length")
        self.items = list(items)
        self.vectors = _normalize(vectors) if len(items) else np.zeros((0, 0), np.float32)

    def search(self, query: np.ndarray, k: int = 50) -> list[Neighbor]:
        if not self.items:
            return []
        sims = self.vectors @ _normalize(query)[0]
        order = np.argsort(-sims)[:k]
        return [Neighbor(self.items[i], float(sims[i])) for i in order]


def aggregate(
    neighbors: list[Neighbor],
    temperature: float = 0.05,
    max_specimens_per_taxon: int = 3,
) -> list[TaxonScore]:
    best_per_specimen: dict[str, Neighbor] = {}
    for n in neighbors:
        cur = best_per_specimen.get(n.item.specimen_id)
        if cur is None or n.similarity > cur.similarity:
            best_per_specimen[n.item.specimen_id] = n

    per_taxon: dict[str, list[Neighbor]] = {}
    for n in sorted(best_per_specimen.values(), key=lambda x: -x.similarity):
        bucket = per_taxon.setdefault(n.item.taxon_id, [])
        if len(bucket) < max_specimens_per_taxon:
            bucket.append(n)
    if not per_taxon:
        return []

    top_sim = max(n.similarity for ns in per_taxon.values() for n in ns)
    raw = {
        t: sum(np.exp((n.similarity - top_sim) / temperature) for n in ns)
        for t, ns in per_taxon.items()
    }
    total = sum(raw.values())
    scores = [
        TaxonScore(
            taxon_id=t,
            probability=float(v / total),
            best_similarity=per_taxon[t][0].similarity,
            supporting_specimens=tuple(n.item.specimen_id for n in per_taxon[t]),
        )
        for t, v in raw.items()
    ]
    return sorted(scores, key=lambda s: -s.probability)


def decide(
    candidates: list[TaxonScore],
    ood_similarity: float = 0.35,
    accept_probability: float = 0.6,
    min_margin: float = 0.2,
    min_specimens: int = 2,
) -> Decision:
    if not candidates:
        return Decision("unknown", [], "Reference set is empty.")
    top = candidates[0]
    if top.best_similarity < ood_similarity:
        return Decision("unknown", candidates[:3], "Nothing in the reference set looks similar enough.")
    margin = top.probability - (candidates[1].probability if len(candidates) > 1 else 0.0)
    if top.probability < accept_probability or margin < min_margin:
        return Decision("uncertain", candidates[:3], "Several candidates are close.")
    if len(top.supporting_specimens) < min_specimens:
        return Decision("uncertain", candidates[:3], "Match rests on a single reference specimen.")
    return Decision("identified", candidates[:3])
