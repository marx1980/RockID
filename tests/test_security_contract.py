"""The identifier must never be able to see challenge credentials, networks, labels or code."""
import ast
import csv
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
IDENTIFIER_SIDE = ["services/api", "services/identifier"]


def _env(service: dict) -> dict:
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = dict(e.split("=", 1) for e in env)
    return env


def test_api_has_no_challenge_credentials():
    api = COMPOSE["services"]["api"]
    assert not [k for k in _env(api) if "CHALLENGE" in k.upper()]
    assert "env_file" not in api
    assert not any("challenge" in str(v).lower() for v in _env(api).values())


def test_api_cannot_reach_challenge_network():
    api_nets = set(COMPOSE["services"]["api"].get("networks") or [])
    assert api_nets, "api must be on an explicit network, not the default one"
    vault_nets = set(COMPOSE["services"]["challenge-db"].get("networks") or [])
    assert vault_nets, "challenge-db must be on an explicit network"
    assert api_nets.isdisjoint(vault_nets)
    assert COMPOSE["networks"]["challenge"].get("internal") is True


def test_only_challenge_db_mounts_challenge_schema():
    for name, svc in COMPOSE["services"].items():
        mounts = " ".join(str(v) for v in svc.get("volumes") or [])
        if name != "challenge-db":
            assert "db/challenge" not in mounts and "challenge_data" not in mounts, name


def test_docker_image_excludes_secrets_and_challenge_material():
    ignored = (ROOT / ".dockerignore").read_text().split()
    for entry in [".env", ".env.*", "data_manifests/challenge", "infra/db/challenge"]:
        assert entry in ignored
    assert "!.env.example" not in ignored


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_identifier_code_never_imports_evaluator_or_challenge_code():
    for d in IDENTIFIER_SIDE:
        for py in (ROOT / d).rglob("*.py"):
            for mod in _imports(py):
                assert not mod.startswith("services.evaluator"), f"{py} imports {mod}"
                assert "challenge" not in mod.lower(), f"{py} imports {mod}"
            assert "CHALLENGE_DATABASE_URL" not in py.read_text(), py


def test_reference_manifests_carry_no_challenge_columns():
    from services.ingestion.manifest import check_header

    for path in (p for p in (ROOT / "data_manifests/reference").glob("*.csv") if p.name != "quarantine.csv"):
        with path.open() as fh:
            header = next(csv.reader(fh))
        assert check_header(header) == [], path.name


def test_no_label_bearing_challenge_manifests_committed():
    files = [p for p in (ROOT / "data_manifests/challenge").rglob("*") if p.is_file()]
    assert [p.name for p in files] == ["README.md"]
