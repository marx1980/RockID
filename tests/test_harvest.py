"""Phase 1: candidate harvesting and promotion. Spec: docs/IMPLEMENTATION_PLAN.md, P1 Tests."""
import csv
import json
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
import pytest
from PIL import Image

from services.ingestion.candidates import CANDIDATE_COLUMNS, read_candidates, write_candidates
from services.ingestion.harvest import harvest
from services.ingestion.licence import propose_usage
from services.ingestion.manifest import validate_file
from services.ingestion.promote import promote
from services.ingestion.sources import commons, smithsonian

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("licence,expected", [
    ("CC0", "allowed_train"),
    ("CC0 1.0", "allowed_train"),
    ("Public domain", "allowed_train"),
    ("PD-self", "allowed_train"),
    ("CC BY 4.0", "allowed_reference_only"),
    ("CC BY-SA 3.0", "allowed_reference_only"),
    ("CC BY-NC 2.0", "rejected"),
    ("CC BY-NC-SA 4.0", "rejected"),
    ("CC BY-ND 4.0", "rejected"),
    ("", "rejected"),
    ("All rights reserved", "rejected"),
])
def test_licence_policy(licence, expected):
    assert propose_usage(licence)[0] == expected


def _mock(routes: dict[str, bytes | dict]):
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        for prefix, body in routes.items():
            if str(req.url).startswith(prefix):
                if isinstance(body, dict):
                    return httpx.Response(200, json=body)
                return httpx.Response(200, content=body, headers={"content-type": "image/jpeg"})
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_commons_parsing():
    client, seen = _mock({commons.API: json.loads((FIX / "commons_azurite.json").read_text())})
    rows = commons.search(client, "min.azurite", "azurite mineral specimen", ["azurite"], limit=10)
    assert "User-Agent" in seen[0].headers and "RockID" in seen[0].headers["User-Agent"]
    by_title = {r.title: r for r in rows}
    assert "File:Azurite diagram.svg" not in by_title  # non-photo mime dropped
    a = by_title["File:Azurite-Malachite-Bisbee-12.jpg"]
    assert a.media_url.endswith("1024px.jpg")
    assert a.author == "Example Photographer"  # HTML stripped
    assert a.license == "CC BY-SA 4.0" and a.proposed_usage == "allowed_reference_only"
    assert a.specimen_hint_confidence == "low"
    # photos 12 and 13 of the same series share a specimen hint
    assert a.specimen_hint == by_title["File:Azurite-Malachite-Bisbee-13.jpg"].specimen_hint
    pendant = by_title["File:Blue pendant necklace.jpg"]
    assert pendant.taxon_in_title is False and pendant.proposed_usage == "rejected"


def test_smithsonian_parsing():
    client, seen = _mock({smithsonian.API: json.loads((FIX / "smithsonian_azurite.json").read_text())})
    rows = smithsonian.search(client, "min.azurite", "azurite", ["azurite"], limit=10, api_key="k")
    assert seen[0].url.params["api_key"] == "k"
    assert {r.media_url for r in rows} == {
        "https://ids.si.edu/ids/deliveryService?id=NMNH-1&max=1024",
        "https://ids.si.edu/ids/deliveryService?id=NMNH-2&max=1024",
    }  # non-CC0 media and other departments dropped
    r = rows[0]
    assert r.specimen_hint == "si:nmnhmineralsciences_1234567" and r.specimen_hint_confidence == "high"
    assert r.license == "CC0" and r.proposed_usage == "allowed_train"
    assert r.author == "Chip Clark"
    assert r.review_decision == ""  # never pre-approved


def test_harvest_writes_deduplicated_candidates(tmp_path):
    client, _ = _mock({
        commons.API: json.loads((FIX / "commons_azurite.json").read_text()),
        smithsonian.API: json.loads((FIX / "smithsonian_azurite.json").read_text()),
    })
    out = tmp_path / "c.csv"
    n = harvest(client, sources=["commons", "smithsonian"], taxa=["min.azurite"], per_taxon=10, out=out, si_api_key="k")
    again = harvest(client, sources=["commons", "smithsonian"], taxa=["min.azurite"], per_taxon=10, out=out, si_api_key="k")
    rows = read_candidates(out)
    assert n == len(rows) == 5 and again == 0  # second run adds nothing new
    with out.open() as fh:
        assert next(csv.reader(fh)) == CANDIDATE_COLUMNS
    assert {r.taxon_id for r in rows} == {"min.azurite"}


def _jpeg(seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    img = Image.fromarray(rng.integers(0, 255, (24, 32, 3), dtype=np.uint8)).resize((640, 480), Image.BICUBIC)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def test_promote_only_reviewed_rows(tmp_path):
    client, _ = _mock({smithsonian.API: json.loads((FIX / "smithsonian_azurite.json").read_text())})
    rows = smithsonian.search(client, "min.azurite", "azurite", ["azurite"], limit=10, api_key="k")
    rows[0] = rows[0].with_review("approve_train")
    rows[1] = rows[1].with_review("")  # not yet reviewed
    cand = tmp_path / "cand.csv"
    write_candidates(cand, rows)

    img_client, _ = _mock({rows[0].media_url: _jpeg(1), rows[1].media_url: _jpeg(2)})
    manifest = tmp_path / "reference.csv"
    result = promote(img_client, cand, manifest, tmp_path / "images", retrieval_date="2026-11-13")

    assert result.promoted == 1 and result.skipped_unreviewed == 1
    assert validate_file(manifest) == []
    with manifest.open() as fh:
        row = next(csv.DictReader(fh))
    assert row["usage_decision"] == "allowed_train" and row["specimen_id"] == "si:nmnhmineralsciences_1234567"
    assert (tmp_path / "images" / f"{row['sha256']}.jpg").exists()


def test_promote_refuses_review_that_exceeds_licence(tmp_path):
    client, _ = _mock({commons.API: json.loads((FIX / "commons_azurite.json").read_text())})
    rows = commons.search(client, "min.azurite", "azurite", ["azurite"], limit=10)
    nc = next(r for r in rows if r.license.startswith("CC BY-NC")).with_review("approve_train")
    cand = tmp_path / "cand.csv"
    write_candidates(cand, [nc])
    img_client, _ = _mock({nc.media_url: _jpeg(3)})
    result = promote(img_client, cand, tmp_path / "ref.csv", tmp_path / "images", retrieval_date="2026-11-13")
    assert result.promoted == 0 and result.refused_licence == 1


def test_promote_skips_exact_duplicates(tmp_path):
    client, _ = _mock({smithsonian.API: json.loads((FIX / "smithsonian_azurite.json").read_text())})
    rows = [r.with_review("approve_train") for r in
            smithsonian.search(client, "min.azurite", "azurite", ["azurite"], limit=10, api_key="k")]
    cand = tmp_path / "cand.csv"
    write_candidates(cand, rows)
    same = _jpeg(7)
    img_client, _ = _mock({rows[0].media_url: same, rows[1].media_url: same})
    result = promote(img_client, cand, tmp_path / "ref.csv", tmp_path / "images", retrieval_date="2026-11-13")
    assert result.promoted == 1 and result.duplicates == 1


def test_every_taxon_has_harvest_queries():
    from services.ingestion.harvest import load_queries
    assert len(load_queries()) == 21


def test_other_taxa_flag():
    client, _ = _mock({commons.API: json.loads((FIX / "commons_azurite.json").read_text())})
    rows = {r.title: r for r in commons.search(client, "min.azurite", "azurite", ["azurite"], limit=10)}
    assert rows["File:Azurite-Malachite-Bisbee-12.jpg"].other_taxa_in_title == "min.malachite"


def test_rate_limit_stops_source_but_not_others(tmp_path):
    calls = {"si": 0}

    def handler(req):
        if str(req.url).startswith(smithsonian.API):
            calls["si"] += 1
            return httpx.Response(429)
        return httpx.Response(200, json=json.loads((FIX / "commons_azurite.json").read_text()))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    n = harvest(client, ["smithsonian", "commons"], ["min.azurite", "min.calcite"], 10, tmp_path / "c.csv")
    assert calls["si"] == 1 and n == 3


def test_duplicates_inside_one_response_are_dropped(tmp_path):
    data = json.loads((FIX / "smithsonian_azurite.json").read_text())
    data["response"]["rows"].append(data["response"]["rows"][0])
    client, _ = _mock({smithsonian.API: data})
    n = harvest(client, ["smithsonian"], ["min.azurite"], 10, tmp_path / "c.csv", si_api_key="k")
    ids = [c.candidate_id for c in read_candidates(tmp_path / "c.csv")]
    assert n == len(ids) == len(set(ids)) == 2


def test_nhm_parsing_and_filters():
    from services.ingestion.sources import nhm

    nhm._cache.clear()
    client, seen = _mock({nhm.API: json.loads((FIX / "nhm_records.json").read_text())})
    marble = nhm.search(client, "rock.marble", ["marble"], limit=50)
    assert "User-Agent" in seen[0].headers and "RockID" in seen[0].headers["User-Agent"]
    assert marble and all(c.source_name == nhm.SOURCE and c.specimen_hint.startswith("nhm:") for c in marble)
    assert all(c.license == "CC BY 4.0" and c.proposed_usage == "allowed_reference_only" for c in marble)
    assert all(c.media_url.startswith("https://data.nhm.ac.uk/media/") and "/full/" not in c.media_url for c in marble)
    assert len({c.candidate_id for c in marble}) == len(marble)
    granite = nhm.search(client, "rock.granite", ["granite"], limit=50)
    titles = " | ".join(c.title for c in granite)
    assert "Wolframite" not in titles  # granite only as the host rock
    assert "Quartz-porphyry" not in " | ".join(c.title for c in nhm.search(client, "min.quartz", ["quartz"], 50))
    everything = [c for t in ("rock.marble", "rock.granite", "rock.limestone", "min.quartz", "rock.basalt") for c in nhm.search(client, t, [t.split(".")[1]], 50)]
    assert not any("box" in c.title.lower() for c in everything)


def test_nhm_limit_and_order_are_deterministic():
    from services.ingestion.sources import nhm

    nhm._cache.clear()
    client, _ = _mock({nhm.API: json.loads((FIX / "nhm_records.json").read_text())})
    a = nhm.search(client, "rock.granite", ["granite"], limit=2)
    b = nhm.search(client, "rock.granite", ["granite"], limit=2)
    assert [c.candidate_id for c in a] == [c.candidate_id for c in b] and len(a) <= 2


def test_nhm_licence_labels():
    from services.ingestion.sources import nhm

    assert nhm.licence_label("http://creativecommons.org/licenses/by/4.0/") == "CC BY 4.0"
    assert nhm.licence_label("http://creativecommons.org/licenses/by-nc/4.0/") == "CC BY-NC 4.0"
    assert propose_usage(nhm.licence_label("http://creativecommons.org/licenses/by-nc/4.0/"))[0] == "rejected"
    assert nhm.licence_label("http://creativecommons.org/publicdomain/zero/1.0/") == "CC0"
    assert nhm.licence_label("") == ""


def test_europeana_parsing_and_filters():
    from services.ingestion.sources import europeana

    client, seen = _mock({europeana.API: json.loads((FIX / "europeana_items.json").read_text())})
    mag = europeana.search(client, "min.magnetite", ["magnetite"], 50, "KEY")
    assert seen[0].url.params["wskey"] == "KEY" and seen[0].url.params["reusability"] == "open"
    assert "RockID" in seen[0].headers["User-Agent"]
    assert mag and all(c.taxon_id == "min.magnetite" and c.source_name.startswith("Europeana: ") for c in mag)
    assert all(c.proposed_usage == "allowed_reference_only" and c.license == "CC BY-SA 4.0" for c in mag if c.license == "CC BY-SA 4.0")
    granite = europeana.search(client, "rock.granite", ["granite"], 50, "KEY")
    assert granite and not any("quarry" in c.title.lower() for c in granite)  # views/quarries dropped
    quartz = europeana.search(client, "min.quartz", ["quartz"], 50, "KEY")
    assert not any("porphyry" in c.title.lower() for c in quartz)
    marble = {c.candidate_id for c in europeana.search(client, "rock.marble", ["marble"], 50, "KEY")}
    assert "eu:/9/neg3" not in marble and "eu:/9/neg4" not in marble  # rights reserved / NC are dropped
    assert all(c.author == c.source_name or c.author for c in mag) and all(c.specimen_hint == f"eu:{c.source_record_id}" for c in mag)


def test_europeana_skipped_without_key(tmp_path):
    out = tmp_path / "c.csv"
    logs = []
    client, _ = _mock({})
    n = harvest(client, ["europeana"], ["min.magnetite"], 5, out, log=logs.append)
    assert n == 0 and any("EUROPEANA_API_KEY" in m for m in logs)


def test_commons_places_queries_each_locality(tmp_path):
    from services.ingestion.harvest import load_localities
    places = load_localities()["rock.marble"]
    client, seen = _mock({commons.API: json.loads((FIX / "commons_azurite.json").read_text())})
    harvest(client, ["commons-places"], ["rock.marble"], 5, tmp_path / "c.csv")
    queried = [r.url.params["gsrsearch"] for r in seen]
    assert len(queried) >= len(places)
    assert any(q.startswith("Carrara marble") for q in queried)
    assert {c for c in load_localities()} <= set(__import__("services.ingestion.harvest", fromlist=["load_queries"]).load_queries())


def test_wikipedia_article_images(tmp_path):
    from services.ingestion.sources import wikipedia
    commons_page = {"pageid": 7, "title": "File:Glimmerite Namibia.jpg", "imageinfo": [{
        "mime": "image/jpeg", "descriptionurl": "https://commons.wikimedia.org/wiki/File:Glimmerite_Namibia.jpg",
        "thumburl": "https://upload.wikimedia.org/x/1024px-G.jpg",
        "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": "Ann"}}}]}

    def handler(req):
        if str(req.url).startswith(wikipedia.WIKI_API):
            return httpx.Response(200, json={"query": {"pages": [{"title": "Biotite", "images": [
                {"title": "File:Glimmerite Namibia.jpg"}, {"title": "File:Structure.svg"}, {"title": "File:Local only.jpg"}]}]}})
        return httpx.Response(200, json={"query": {"pages": [commons_page,
            {"title": "File:Local only.jpg", "missing": True}, {"pageid": 8, "title": "File:Structure.svg", "imageinfo": [{"mime": "image/svg+xml"}]}]}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found = wikipedia.search(client, "min.biotite", ["Biotite"], ["biotite"])
    assert [c.candidate_id for c in found] == ["commons:7"]
    assert found[0].taxon_in_title and found[0].proposed_usage == "allowed_reference_only"
    n = harvest(client, ["wikipedia"], ["min.biotite"], 10, tmp_path / "c.csv")
    assert n == 1


def test_every_taxon_has_wikipedia_articles():
    from services.ingestion.harvest import load_articles, load_queries
    assert set(load_articles()) == set(load_queries())
