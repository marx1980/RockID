from types import SimpleNamespace

from services.curation.contact_sheet import diversify


def cand(i, taxon, author):
    return SimpleNamespace(candidate_id=f"c{i}", taxon_id=taxon, author=author, specimen_hint=f"s{i}")


def test_diversify_caps_author_and_round_robins():
    cs = [cand(i, "rock.granite", "A") for i in range(10)] + [cand(100 + i, "rock.granite", "B") for i in range(2)]
    out = diversify(cs, per_author=3, per_taxon=4)
    ids = {c.candidate_id for c in out}
    assert len(out) == 4
    assert {"c100", "c101"} <= ids  # the second photographer is not crowded out


def test_diversify_skips_authors():
    cs = [cand(1, "rock.marble", "Internet Archive Book Images"), cand(2, "rock.marble", "B")]
    assert [c.candidate_id for c in diversify(cs, 5, 0, ("Internet Archive",))] == ["c2"]
