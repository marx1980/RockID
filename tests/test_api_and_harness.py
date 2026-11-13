from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from packages.taxonomy.loader import load_taxonomy
from services.api.app.main import app
from services.evaluator.harness import (
    InMemoryChallengeStore, NotFrozenError, PredictionLedger, RevealedTruth, run_suite,
)
from services.evaluator.metrics import UNKNOWN, report
from services.identifier.pipeline import Identifier
from tests.test_identifier import FakeEncoder, _index

client = TestClient(app)


def _jpeg(size=(400, 400), seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    img = Image.fromarray(rng.integers(40, 215, (*size[::-1], 3), dtype=np.uint8))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_identifier():
    yield
    app.state.identifier = None


def test_health_reports_no_challenge_credentials():
    body = client.get("/health").json()
    assert body["challenge_credentials_present"] is False
    assert body["model_loaded"] is False


def test_rejects_non_images_and_unsupported_formats():
    assert client.post("/v1/identify", files={"image": ("x.jpg", b"not an image")}).status_code == 422
    assert client.post("/v1/identify", files={"image": ("x.jpg", b"")}).status_code == 422
    buf = BytesIO()
    Image.new("RGB", (300, 300)).save(buf, "GIF")
    assert client.post("/v1/identify", files={"image": ("x.gif", buf.getvalue())}).status_code == 415


def test_baseline_abstains_honestly():
    body = client.post("/v1/identify", files={"image": ("x.jpg", _jpeg())}).json()
    assert body["status"] == "need_more_evidence"
    assert body["top_candidates"] == []
    assert body["best_follow_up"]["type"] == "model_required"
    assert body["taxonomy_version"] == "mvp21-v1"


def test_poor_photo_gets_retake_follow_up():
    body = client.post("/v1/identify", files={"image": ("x.jpg", _jpeg(size=(120, 120)))}).json()
    assert body["best_follow_up"]["type"] == "retake_photo"
    assert "too_small" in body["image_quality"]["issues"]


def test_with_identifier_installed():
    app.state.identifier = Identifier(FakeEncoder([1, 0, 0, 0]), _index(), load_taxonomy())
    body = client.post("/v1/identify", files={"image": ("x.jpg", _jpeg())}).json()
    assert body["status"] == "identified"
    assert body["top_candidates"][0]["taxon_id"] == "min.quartz"
    assert body["model_version"] == "test:fake@0"


def _api_identify(raw: bytes) -> dict:
    # Same path the real evaluator uses: bytes only, nothing else.
    r = client.post("/v1/identify", files={"image": ("image", raw, "application/octet-stream")})
    r.raise_for_status()
    return r.json()


def test_reveal_requires_frozen_prediction(tmp_path):
    store = InMemoryChallengeStore({"c1": ("collector", _jpeg(), RevealedTruth("min.quartz"))})
    with pytest.raises(NotFrozenError):
        store.reveal("c1", PredictionLedger(tmp_path / "ledger.jsonl"))


def test_blind_run_end_to_end(tmp_path):
    app.state.identifier = Identifier(FakeEncoder([1, 0, 0, 0]), _index(), load_taxonomy())
    seen: list[bytes] = []

    def identify(raw: bytes) -> dict:
        seen.append(raw)
        return _api_identify(raw)

    store = InMemoryChallengeStore({
        "c1": ("collector", _jpeg(seed=1), RevealedTruth("min.quartz")),
        "c2": ("collector", _jpeg(seed=2), RevealedTruth("min.calcite", ("rock.marble",))),
        "c3": ("collector", _jpeg(seed=3), RevealedTruth(UNKNOWN)),
    })
    ledger = PredictionLedger(tmp_path / "ledger.jsonl")
    rows = run_suite(store, "collector", identify, ledger)

    assert all(isinstance(b, bytes) for b in seen) and len(seen) == 3
    assert all(ledger.is_frozen(c) for c in ("c1", "c2", "c3"))
    with pytest.raises(ValueError):
        ledger.freeze("c1", {})  # predictions are immutable
    r = report(rows)
    assert r["cases"] == 3 and r["ood_cases"] == 1
    assert r["top1"] == 0.5  # fake encoder always says quartz
    assert r["unknown_false_accept_rate"] == 1.0

    # Re-running reuses frozen predictions instead of re-asking the identifier.
    run_suite(store, "collector", identify, PredictionLedger(tmp_path / "ledger.jsonl"))
    assert len(seen) == 3
