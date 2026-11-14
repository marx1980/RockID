"""Build the review site: compact candidates.json + taxa.json + the review page.

  python -m services.review.build_site data_manifests/candidates/candidates.csv site/
"""
import json
import shutil
import sys
from pathlib import Path

from packages.taxonomy.loader import load_taxonomy
from services.ingestion.candidates import read_candidates
from services.ingestion.decisions import load_decisions

PAGE = Path(__file__).resolve().parents[2] / "apps/review/index.html"


def build_site(candidates_csv: str | Path, out_dir: str | Path, decisions_path: str | Path | None = None) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # Policy-rejected candidates (non-commercial, unknown licence, wrong subject) are never shown.
    # Challenge-reserved photos never appear in the review UI.
    reserved = {k for k, v in load_decisions(decisions_path).items() if v == "reserve"}
    rows = [c for c in read_candidates(candidates_csv) if c.proposed_usage != "rejected" and c.candidate_id not in reserved]
    rows.sort(key=lambda c: (c.taxon_id, c.specimen_hint, c.candidate_id))
    data = [
        {
            "id": c.candidate_id, "t": c.taxon_id, "ti": c.title, "u": c.source_url, "m": c.media_url,
            "a": c.author, "l": c.license, "sp": c.specimen_hint, "sc": c.specimen_hint_confidence,
            "pu": c.proposed_usage, "ot": c.other_taxa_in_title,
        }
        for c in rows
    ]
    (out / "candidates.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    taxa = {tid: {"n": t.canonical_name, "c": t.category} for tid, t in load_taxonomy().items()}
    from services.ingestion.harvest import extra_names
    taxa.update({tid: {"n": n, "c": "MINERAL"} for tid, n in extra_names().items()})
    (out / "taxa.json").write_text(json.dumps(taxa, separators=(",", ":")), encoding="utf-8")
    if PAGE.exists():
        shutil.copy(PAGE, out / "index.html")
    return len(data)


if __name__ == "__main__":
    print(build_site(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
