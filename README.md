# Rock ID + RockLab
Executable Phase-0 starter for a rock/mineral photo identifier and isolated blind evaluator.

## Start
```bash
cp .env.example .env
docker compose up --build
```
API: http://localhost:8000/docs

## Test
```bash
python -m pip install -r requirements.txt
pytest -q
```

## Critical invariant
The identifier has no Challenge Vault credentials. Challenge labels are exposed only to the evaluator process. Challenge images may be passed to the identifier as bytes; label/source metadata may not.

## Current state
This is a runnable scaffold, not a trained geology model. `/v1/identify` implements a deterministic baseline contract and abstains rather than inventing a mineral. The next milestone is acquiring license-approved reference and challenge images and benchmarking real DINOv2/SigLIP2 embeddings.
