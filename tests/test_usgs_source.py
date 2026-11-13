from services.ingestion.sources import usgs

IMG = "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/styles/full_width/public/media/images/cockeysville_marble.jpg?itok=abc"
ORIG = "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/media/images/cockeysville_marble.jpg"


def _page(body="Public Domain.", desc="Marble from Maryland."):
    return (f'<html><head><meta property="og:title" content="Cockeysville Marble | U.S. Geological Survey">'
            f'<meta property="og:description" content="{desc}"></head><body><img src="{IMG}"><a href="{ORIG}">download</a>{body}</body></html>')


def test_item_parsed_with_full_width_image_and_public_domain():
    c = usgs.parse_item(_page(), "/media/images/cockeysville-marble", "rock.marble", ["marble"])
    assert c.candidate_id == "usgs:cockeysville-marble" and c.media_url == IMG and c.license == "Public domain"
    assert c.title == "Cockeysville Marble" and c.taxon_in_title and not c.reviewer_note


def test_non_public_domain_page_is_dropped_and_generic_renderings_flagged():
    assert usgs.parse_item(_page(body="All rights reserved"), "/media/images/x-marble", "rock.marble", ["marble"]) is None
    c = usgs.parse_item(_page(desc="High-definition image of calcite marble"), "/media/images/calcite-marble", "rock.marble", ["marble"])
    assert "machine-generated" in c.reviewer_note


def test_listing_links_found():
    html = '<a href="/media/images/barre-granite">a</a><a href="https://www.usgs.gov/media/images/cockeysville-marble">b</a><a href="/media/images/barre-granite">c</a>'
    assert list(dict.fromkeys(usgs.ITEM.findall(html))) == ["/media/images/barre-granite", "/media/images/cockeysville-marble"]
