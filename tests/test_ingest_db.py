"""G-03 round trip: candidates -> review decisions -> promote -> manifest -> reference DB.
DB tests need TEST_DATABASE_URL (a throwaway database); CI provides one, locally they skip."""
import json
import os
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
import pytest
from PIL import Image

from services.ingestion.candidates import read_candidates, write_candidates
from services.ingestion.decisions import validate_decisions
from services.ingestion.ingest_db import IngestError, ingest
from services.ingestion.manifest import validate_file
from services.ingestion.promote import promote
from tests.test_promote_v2 import _cand, _client, _jpg, _texture

DB_URL = os.getenv("TEST_DATABASE_URL")
SCHEMA = Path(__file__).resolve().parents[1] / "infra/db/reference/001_init.sql"
needs_db = pytest.mark.skipif(not DB_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def conn():
    import psycopg

    with psycopg.connect(DB_URL, autocommit=True) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public; CREATE EXTENSION IF NOT EXISTS vector;")
        c.execute(SCHEMA.read_text())
        yield c


def _build_manifest(tmp_path):
    cands = [
        _cand(1, "min.quartz", specimen="q", review=""),
        _cand(2, "min.quartz", specimen="q", review=""),
        _cand(3, "min.calcite", specimen="c", licence="CC BY-SA 4.0", usage="allowed_reference_only", review=""),
        _cand(4, "rock.granite", specimen="g", review=""),
        _cand(5, "rock.granite", specimen="g", review=""),
    ]
    cand_csv = tmp_path / "cand.csv"
    write_candidates(cand_csv, cands)
    decisions = {"t:1": "approve_train", "t:2": "approve_train", "t:3": "approve_reference", "t:4": "reject"}
    assert validate_decisions(read_candidates(cand_csv), decisions) == []
    (tmp_path / "d.json").write_text(json.dumps(decisions))
    files = {f"https://img/{i}.jpg": _jpg(_texture(100 + i)) for i in range(1, 6)}
    promote(_client(files), cand_csv, tmp_path / "ref.csv", None, retrieval_date="2026-11-13",
            decisions_path=tmp_path / "d.json")
    assert validate_file(tmp_path / "ref.csv") == []
    return tmp_path / "ref.csv"


@needs_db
def test_round_trip_into_reference_db(tmp_path, conn):
    manifest = _build_manifest(tmp_path)
    res = ingest(conn, manifest)
    assert (res.taxa, res.specimens, res.assets_inserted) == (21, 3, 3)
    q = lambda sql: conn.execute(sql).fetchall()
    assert q("select count(*) from assets where usage_decision='allowed_train'") == [(2,)]
    assert q("select count(*) from assets where usage_decision='allowed_reference_only'") == [(1,)]
    assert q("select taxon_id from specimens order by 1") == [("min.calcite",), ("min.quartz",), ("min.quartz",)]
    assert q("select media_url from assets where asset_id='t:3'") == [("https://img/3.jpg",)]
    # no unreviewed (t:5) or rejected (t:4) candidate reached the DB
    assert q("select count(*) from assets where asset_id in ('t:4','t:5')") == [(0,)]


@needs_db
def test_ingest_is_idempotent(tmp_path, conn):
    manifest = _build_manifest(tmp_path)
    ingest(conn, manifest)
    again = ingest(conn, manifest)
    assert again.assets_inserted == 0 and again.assets_existing == 3
    assert conn.execute("select count(*) from assets").fetchone() == (3,)


@needs_db
def test_invalid_manifest_never_touches_db(tmp_path, conn):
    manifest = _build_manifest(tmp_path)
    manifest.write_text(manifest.read_text().replace("allowed_train", "pending", 1))
    with pytest.raises(IngestError):
        ingest(conn, manifest)
    assert conn.execute("select count(*) from assets").fetchone() == (0,)


@needs_db
def test_taxonomy_sync_matches_csv(tmp_path, conn):
    ingest(conn, _build_manifest(tmp_path))
    assert conn.execute("select count(*) from taxa where confusion_group <> ''").fetchone() == (21,)
