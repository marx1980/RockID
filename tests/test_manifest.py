

def test_manifest_accepts_extra_taxa():
    from packages.taxonomy.loader import extra_taxon_ids
    from services.ingestion.manifest import validate_rows
    tid = sorted(extra_taxon_ids())[0]
    row = {"asset_id": "x:1", "taxon_id": tid, "specimen_id": "s1", "source_name": "t", "source_url": "u", "author": "a",
           "license": "CC0", "retrieval_date": "2026-01-01", "usage_decision": "approve_reference",
           "sha256": "a" * 64, "phash": "0" * 16, "media_url": "m", "form": "natural"}
    assert not [e for e in validate_rows([row]) if "unknown taxon" in e.problem]
