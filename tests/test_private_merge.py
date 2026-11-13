import json

import numpy as np
import pytest

from services.model.private import merge


def _write(prefix, n, model="m", start=0):
    np.arange(n * 3, dtype=np.float32).tofile(f"{prefix}.f32")
    items = [{"id": f"{prefix.name}{i + start}", "s": f"s{i}", "t": "min.quartz"} for i in range(n)]
    (prefix.parent / f"{prefix.name}.json").write_text(json.dumps({"model": model, "dtype": "q8", "dim": 3, "items": items, "failed": []}))


def test_private_vectors_are_appended_and_model_must_match(tmp_path):
    _write(tmp_path / "ref", 2)
    _write(tmp_path / "pri", 3)
    assert merge(str(tmp_path / "ref"), [str(tmp_path / "pri")]) == {"reference": 2, "private": 3}
    meta = json.loads((tmp_path / "ref.json").read_text())
    assert len(meta["items"]) == 5 and np.fromfile(tmp_path / "ref.f32", dtype=np.float32).size == 15
    _write(tmp_path / "other", 1, model="x")
    with pytest.raises(SystemExit):
        merge(str(tmp_path / "ref"), [str(tmp_path / "other")])
