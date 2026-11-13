import httpx

from services.ingestion import ood_harvest
from services.ingestion.candidates import read_candidates


def _page(i):
    return {"pageid": i, "title": f"File:Thing {i}.jpg", "imageinfo": [{
        "mime": "image/jpeg", "url": f"https://u/{i}.jpg", "thumburl": f"https://t/{i}.jpg", "descriptionurl": f"https://d/{i}",
        "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": "Ann"}}}]}


def test_ood_groups_loaded_and_files_labelled(tmp_path):
    groups = ood_harvest.load_groups()
    assert set(groups) == {"ood.other_mineral", "ood.other_rock", "ood.man_made", "ood.other_natural"}

    def handler(req):
        return httpx.Response(200, json={"query": {"pages": [_page(1), _page(2)]}})

    out = tmp_path / "o.csv"
    n = ood_harvest.harvest(httpx.Client(transport=httpx.MockTransport(handler)), out, per_category=5)
    rows = read_candidates(out)
    assert n == len(rows) == 2  # the same two files under every category are kept once
    assert {r.taxon_id for r in rows} == {"ood.other_mineral"}
