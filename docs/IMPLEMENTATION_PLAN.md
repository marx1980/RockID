# Implementation plan

One phase per session. Each phase lists Tests (written first) and a Gate. G-nn gates are automated, H-nn need Marko.

| Phase | Model | Effort |
|---|---|---|
| P1 Candidate harvesting | Sonnet 5.5 | high |
| P2 Review tool + reference DB ingest | Sonnet 5.5 | high |
| P3 Embeddings + pgvector index | Opus 5.5 | high |
| P4 Challenge set + evaluator service + first baseline | Opus 5.5 | high |
| P5 Calibration, OOD, follow-up questions | Opus 5.5 | high |
| P6 Mobile identify app | Sonnet 5.5 | high |

## P1 Candidate harvesting
Collect candidate photos per taxon with full provenance. Nothing becomes reference data without a human review decision.
- Sources: Smithsonian NMNH Mineral Sciences (CC0, one record = one specimen) and Wikimedia Commons (per-file licences, specimen guessed).
- Licence policy in `services/ingestion/licence_policy.csv` proposes a usage; `promote` re-checks it so an approval cannot exceed the licence.
- Harvest runs in GitHub Actions (`harvest-candidates`), because the dev workspace has no outbound network; results land on a `harvest/run-*` branch.

Tests: licence policy table; Commons and Smithsonian parsing (mime filter, CC0 filter, department filter, HTML stripping, specimen hints); harvest idempotent and deduplicated; promote only reviewed rows, refuse approvals the licence does not permit, skip exact duplicates, output passes the manifest validator.

Gate:
- G-01: all tests pass.
- G-02: a live harvest run yields ≥ 5 usable specimens (by hint) for ≥ 15 of 21 taxa.
- H-01: Marko signs off the licence policy (in particular CC BY / CC BY-SA = reference-only) and spot-checks 20 candidates.

## P2 Review tool + reference DB ingest
- Phone-friendly review page over the candidates CSV: thumbnail grid per taxon, approve train / approve reference / reject, export CSV.
- `promote` into the reference DB (taxa, specimens, assets) with near-duplicate quarantine.
- Storage decision for images (local volume vs object store).

Gate: G-03 round-trip candidates → review → manifest → DB with zero validator errors; H-02 Marko reviews ≥ 1 taxon end to end on the phone.

## P3 Embeddings + pgvector index
- Embed approved assets with DINOv2 and SigLIP2 (in Actions or a local machine), register encoder provenance, store vectors.
- Postgres-backed `ReferenceIndex` matching the in-memory contract.

Gate: G-04 same top-k from pgvector and in-memory index on a sample; leave-one-specimen-out sanity accuracy reported (not a benchmark).

## P4 Challenge set + evaluator service + first baseline
- Challenge cases from sources and specimens disjoint from the reference set (`find_split_leakage` must be empty).
- Postgres `ChallengeStore`, evaluator service on both networks, frozen run report.

Gate: G-05 leakage check empty; G-06 report produced for both encoders; H-03 Marko reads the first honest baseline.

## P5 Calibration, OOD, follow-ups
Tune abstention thresholds on a calibration split (never on the frozen suite), add OOD corpus, structured follow-up prompts (streak, hardness, fresh surface).

## P6 Mobile identify app
Camera capture, quality retake prompts, candidates with evidence, follow-up flow.
