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
- Phone-first review page on GitHub Pages (`apps/review`, built by `services/review/build_site.py`): one photo at a time with Reject / Reference / Train, grid view, undo, per-taxon progress. Policy-rejected candidates are never shown; Train is disabled unless the licence policy allows it.
- Decisions live in `data_manifests/candidates/decisions.json`, separate from the harvested candidates so a harvest re-run cannot overwrite them. The page saves locally first and commits to the repo with a fine-grained token (optional).
- `promote` applies decisions, re-checks the licence, downloads to fingerprint and verify (images are not stored), quarantines near-duplicate photos (pHash distance ≤ 4, rotation/mirror invariant) into `quarantine.csv`, and writes `reference.csv` including `media_url`.
- `ingest_db` loads the manifest into the reference Postgres (taxa, specimens, assets), idempotently; an invalid manifest changes nothing.

Tests: decisions overlay and validation; site build; promote with decisions, quarantine, optional image storage, `media_url`; one specimen cannot span two taxa; Postgres round trip, idempotence, invalid manifest rejected; review page driven in headless Chrome at phone size.

Gate:
- G-03: round trip candidates → decisions → manifest → DB with zero validator errors (automated, fixtures; repeated on real data after review).
- H-02: Marko reviews at least one taxon end to end on the phone and the resulting manifest passes validation.

## P3 Embeddings + in-app model
- DINOv2-small (int8 ONNX) via transformers.js in the build job and on the phone, same code (`app/model/core.mjs`).
- `build-model` workflow: embed reference set, calibrate thresholds on reference leave-one-specimen-out, embed challenge (ids + URLs only), score once, push `app/model/*` and `results/*` to a branch.
- App loads the model on first identify and ranks taxa by specimen-balanced k-NN.

Tests: JS vs Python decisions on the same vectors; embedding maths; calibration and scoring on synthetic clusters; app flow in headless Chrome.

Gate: G-04 build succeeds with < 5% images failing to embed; G-05 baseline report produced; H-03 Marko tries the app on real rocks.

## P4 Challenge set + evaluator service + first baseline
- Challenge cases from sources and specimens disjoint from the reference set (`find_split_leakage` must be empty).
- Postgres `ChallengeStore`, evaluator service on both networks, frozen run report.

Gate: G-05 leakage check empty; G-06 report produced for both encoders; H-03 Marko reads the first honest baseline.

## P5 Calibration, OOD, follow-ups
Tune abstention thresholds on a calibration split (never on the frozen suite), add OOD corpus, structured follow-up prompts (streak, hardness, fresh surface).

## P6 Mobile identify app
Camera capture, quality retake prompts, candidates with evidence, follow-up flow.
