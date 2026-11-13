# Rock ID + RockLab
Phase-0 starter for a rock/mineral photo identifier and an isolated blind evaluator.

## Start
```bash
docker compose up --build
```
API: http://localhost:8000/docs

## Test
```bash
python -m pip install -r requirements-dev.txt
pytest   # set TEST_DATABASE_URL to also run the Postgres tests
python -m services.ingestion.manifest data_manifests/reference/*.csv
```
Real encoders (DINOv2, SigLIP2) need `requirements-ml.txt`.

## Critical invariant
The identifier has no Challenge Vault credentials, network route or code path. Challenge labels are visible only to the evaluator, and only after the prediction for that case is frozen. Challenge images reach the identifier as bytes; label/source metadata never does. `tests/test_security_contract.py` enforces this.

## Layout
| Path | Role |
|---|---|
| `services/api` | `/v1/identify`: upload validation, quality gate, identifier call |
| `services/identifier` | quality gate, encoder adapters, k-NN search, specimen-balanced aggregation, abstention |
| `services/ingestion` | candidate harvesting, review decisions, promote to reference manifest, DB ingest, duplicate and split-leakage detection |
| `services/review`, `apps/review` | phone review page (GitHub Pages) and its site builder |
| `services/evaluator` | blind run harness (freeze then reveal), metrics |
| `packages/taxonomy` | MVP21 taxonomy with stable IDs and confusion groups |
| `infra/db/reference` | pgvector schema (reference domain) |
| `infra/db/challenge` | Challenge Vault schema, append-only predictions |

## Current state
Runnable scaffold, not a trained geology model. With no encoder installed, `/v1/identify` validates the photo, reports image quality and abstains rather than inventing a mineral. The identification path (encoder → reference search → aggregation → abstention) is implemented and tested with synthetic vectors; it needs licence-approved reference images and a calibrated benchmark next. See `PHASE0_TODO.md`.
