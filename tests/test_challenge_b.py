import csv
import json
from dataclasses import replace

from services.curation.challenge_b import build
from services.ingestion.candidates import write_candidates
from tests.test_promote_v2 import _cand


def _c(i, taxon, author):
    return replace(_cand(i, taxon), author=author, source_name="Wikimedia Commons")


def test_whole_photographers_go_to_b_and_reference_overlap_is_excluded(tmp_path):
    cands = [_c(i, "rock.marble", "Ann") for i in range(10)] + [_c(20 + i, "rock.marble", "Bob") for i in range(10)] \
        + [_c(40 + i, "rock.marble", "Cy") for i in range(30)] + [_c(80 + i, "rock.marble", "Dee") for i in range(30)]
    write_candidates(tmp_path / "c.csv", cands)
    (tmp_path / "d.json").write_text(json.dumps({c.candidate_id: "approve_reference" for c in cands}))
    with (tmp_path / "ref.csv").open("w", newline="") as fh:  # Ann already has a reference photo of marble
        w = csv.writer(fh)
        w.writerow(["taxon_id", "author", "source_name", "specimen_id", "source_url"])
        w.writerow(["rock.marble", "Ann", "Wikimedia Commons", "old", "https://old/1"])
    ids = {c.candidate_id for c in cands}
    report = build(tmp_path / "c.csv", tmp_path / "d.json", tmp_path / "ref.csv", ids, tmp_path / "b.csv")
    rows = list(csv.DictReader((tmp_path / "b.csv").open()))
    authors = {r["author"] for r in rows}
    assert "Ann" not in authors and authors
    for a in authors:  # a photographer is never split between B and the reference side
        d = json.loads((tmp_path / "d.json").read_text())
        mine = [c.candidate_id for c in cands if c.author == a]
        assert all(d[i] == "reserve" for i in mine)
    assert report["rock.marble"]["challenge_b"] == len(rows)
