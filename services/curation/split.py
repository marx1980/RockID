"""Split approved candidates into the reference set and the challenge set.

Independence rule: within a taxon, photos are grouped into connected components that share
an author, a specimen or a source page. A whole component goes to one side, so a challenge
photo never shares a photographer, specimen or record with any reference photo of that taxon.
Components are assigned deterministically (hash order) until the challenge side reaches the
target fraction, while the reference side keeps at least `min_reference_specimens` specimens.
"""
import hashlib
from dataclasses import dataclass, field

from services.ingestion.candidates import Candidate


@dataclass
class SplitResult:
    assignment: dict[str, str] = field(default_factory=dict)  # candidate_id -> reference | challenge
    no_challenge: dict[str, str] = field(default_factory=dict)  # taxon -> reason


def _page(url: str) -> str:
    return url.split("#", 1)[0].split("?", 1)[0].rstrip("/").lower()


def _components(items: list[Candidate]) -> list[list[Candidate]]:
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    keys: dict[str, int] = {}
    for i, c in enumerate(items):
        # An institution credited as author (e.g. a museum) is not a photographer: group by specimen only.
        author = "" if (c.author or "").strip() in ("", c.source_name) else c.author.strip().lower()
        for k in (f"a:{author}", f"s:{c.specimen_hint}", f"p:{_page(c.source_url)}"):
            if k.endswith(":"):
                continue
            if k in keys:
                parent[find(i)] = find(keys[k])
            else:
                keys[k] = i
    groups: dict[int, list[Candidate]] = {}
    for i, c in enumerate(items):
        groups.setdefault(find(i), []).append(c)
    return list(groups.values())


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def split(
    candidates: list[Candidate], approved: set[str],
    challenge_fraction: float = 0.25, min_reference_specimens: int = 3,
) -> SplitResult:
    res = SplitResult()
    by_taxon: dict[str, list[Candidate]] = {}
    for c in sorted(candidates, key=lambda c: c.candidate_id):
        if c.candidate_id in approved:
            by_taxon.setdefault(c.taxon_id, []).append(c)

    for taxon, items in sorted(by_taxon.items()):
        comps = sorted(_components(items), key=lambda g: _h(taxon + min(c.candidate_id for c in g)))
        target = challenge_fraction * len(items)
        challenge: list[list[Candidate]] = []
        n_ch = 0
        for g in comps:
            if n_ch >= target:
                break
            remaining = [c for comp in comps if comp is not g and comp not in challenge for c in comp]
            if len({c.specimen_hint for c in remaining}) < min_reference_specimens:
                continue
            if n_ch + len(g) > max(target * 1.6, 2):
                continue
            challenge.append(g)
            n_ch += len(g)
        if len(comps) < 2:
            res.no_challenge[taxon] = "single independent group (one photographer/specimen cluster)"
        elif not challenge:
            res.no_challenge[taxon] = f"too few specimens to keep {min_reference_specimens} in reference"
        ch_ids = {c.candidate_id for g in challenge for c in g}
        for c in items:
            res.assignment[c.candidate_id] = "challenge" if c.candidate_id in ch_ids else "reference"
    return res
