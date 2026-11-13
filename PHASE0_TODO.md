# Phase 0

## Done
- [x] Network, credential and image-level isolation of the Challenge Vault, enforced by tests
- [x] Taxonomy v1 (MVP21): stable taxon IDs, K-feldspar added, confusion groups
- [x] Reference manifest validator (licence, usage decision, specimen ID, hashes, forbidden label columns)
- [x] Rotation/mirror-invariant duplicate check and specimen/source-level split leakage check
- [x] Full metric set: top-k, macro F1, per-class recall, coverage, selective accuracy, confident-error, unknown false-accept, ECE
- [x] Blind evaluation harness: bytes-only identify, append-only prediction ledger, reveal-after-freeze
- [x] Upload validation and image quality gate with retake follow-ups
- [x] Encoder adapter interface + DINOv2 / SigLIP2 adapters with weight provenance (not yet run)
- [x] In-memory k-NN with specimen-balanced aggregation and abstention
- [x] pgvector reference schema and Challenge Vault schema (append-only predictions)
- [x] CI

## Remaining
- Confirm image-training/reuse terms source-by-source before ingestion.
- Acquire diverse, independent specimens for the MVP21 reference set (target ≥ 5 specimens/taxon).
- Acquire isolated challenge cases from different specimens/sources, per suite.
- Add UNKNOWN/OOD corpus (other minerals, man-made objects, non-rocks).
- Run DINOv2 and SigLIP2 on the corpus; persist embeddings in pgvector; add a Postgres-backed `ReferenceIndex`.
- Add a Postgres-backed `ChallengeStore` and an evaluator service on both networks.
- Calibrate pHash and abstention thresholds on the actual corpus.
- Freeze and publish the first honest baseline report.
