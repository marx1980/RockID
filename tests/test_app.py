import json
from pathlib import Path

from services.app.build_data import build, check

ROOT = Path(__file__).resolve().parents[1]


def test_app_data_is_current_and_valid():
    data = build()
    assert check(data) == []
    assert json.loads((ROOT / "app/data.json").read_text()) == data
    assert len(data["taxa"]) == 21 and all(t["hardness"] for t in data["taxa"].values())


def test_every_multi_member_group_has_a_followup():
    data = build()
    groups: dict[str, int] = {}
    for t in data["taxa"].values():
        groups[t["group"]] = groups.get(t["group"], 0) + 1
    assert {g for g, n in groups.items() if n > 1} <= set(data["followups"])
