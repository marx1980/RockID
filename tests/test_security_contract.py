from pathlib import Path

def test_api_compose_has_no_challenge_credentials():
    text=Path("docker-compose.yml").read_text()
    api=text.split("  reference-db:")[0]
    assert "CHALLENGE_DATABASE_URL" not in api

def test_challenge_labels_not_in_reference_manifest():
    header=Path("data_manifests/reference/example.csv").read_text().splitlines()[0]
    assert "ground_truth" not in header
