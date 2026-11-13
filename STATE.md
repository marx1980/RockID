# State

Current phase: **P3b data improvement under way (NHM London added, neutral on the baseline); P4 calibration/OOD after** (see docs/IMPLEMENTATION_PLAN.md)

## Built
- Phase 0 scaffold: isolated Challenge Vault, manifest validator, leakage checks, metrics, blind harness, quality gate, k-NN aggregation, DB schemas, CI
- P1: Smithsonian + Commons connectors, licence policy, idempotent harvest CLI, promote CLI (download, fingerprint, validate), `harvest-candidates` Actions workflow

- P2: review page (apps/review), decisions file + validation, promote with quarantine and media_url, Postgres ingest, review-site / promote-reference workflows, CI with a pgvector Postgres

- Agent curation: contact sheets, visual review of all candidates, reference/challenge split, vault branch
- Identify app (app/): camera-first, quality gate, result/alternatives/check/properties, collection, demo switch

- P3 code: shared JS core (embedding + k-NN + decisions), Node embedder, calibration/scoring, build-model workflow, app integration

## Stubbed / not run
- DINOv2 / SigLIP2 adapters (no weights downloaded)
- Postgres-backed ReferenceIndex and ChallengeStore
- Evaluator service in compose

## Known gaps
- Smithsonian query syntax (`unit_code:` / `online_media_type:` filters) and Commons search quality are verified only against hand-written fixtures until the first live run
- Commons specimen hints are filename heuristics and over-group numbered Flickr series ("Granite 33 (4919…)" → one specimen); safe for leakage, undercounts specimens
- Smithsonian runs need an api.data.gov key (secret SI_API_KEY); DEMO_KEY is rate-limited after ~9 queries
- Review page tested in headless Chrome with mocked images and a mocked GitHub API; not yet opened on a real phone or against live Pages
- Pages must be enabled in repo settings (source: GitHub Actions) before the review-site workflow can deploy
- Near-duplicate threshold (4) and specimen hints are uncalibrated

## Data
- `data_manifests/candidates/candidates.csv`: 1,564 candidates, none reviewed
- Smithsonian rock types harvested with SI_API_KEY (run 43338787634); chert, quartzite and slate have few Smithsonian hits (2, 9, 7)
- 154 candidates name a second MVP taxon in the title (`other_taxa_in_title`)
- Commons marble results include statues and buildings; review must reject them

## Gates
G-01 PASS, G-02 PASS (provisional), H-01 PASS (licence policy approved). Log: results/gate_log.jsonl

## Data after curation
- 839 approved, 597 rejected; 645 reference, 190 challenge (vault branch)
- Thin classes: marble 2, biotite 4, slate 10 approved; chert has no challenge cases; magnetite 1 challenge case
- pHash leakage between reference and challenge not yet checked (needs challenge fingerprints; P4)

## Next (old)
H-02: enable Pages, create the token, review at least one taxon on the phone. Then run promote-reference, ingest to the DB and start P3 (embeddings).


## Baseline (results/BASELINE.md)
- Shortlist: right answer first 48%, in top 3 80%; mineral vs rock 93% (independent photographers and specimens)
- Committed answers: only 15% of photos, 76% correct (reference calibration promised 81%)
- Top confusions: quartz/calcite, malachite/azurite, gypsum/calcite/quartz, K-feldspar/quartzite
- Unverified: real phone camera photos (the benchmark is museum and collector photos)

## Next
1. H-03: Marko tries the app on real rocks.
2. P3b: more and better reference data for weak classes (marble 2, biotite 3, granite 3 specimens; slate, magnetite thin); re-harvest with better queries; consider dinov2-base or SigLIP2 and compare on the same challenge set.
3. P4: OOD set (non-rocks, other minerals), threshold calibration on a held-out calibration split, follow-up answers fed back into ranking.

## P3b so far
- NHM London harvester (services/ingestion/sources/nhm.py), review rounds (contact sheets with prefix, merge_round), tagged re-score
- 634 NHM candidates reviewed visually: 49 approved and promoted, 582 rejected (443 polished slab scans, 120 surplus sandstone)
- Reference set 692 photos; v2 re-score neutral (results/BASELINE_v2.md); live app still on model v1
- Still thin: marble 2, biotite 3, granite 8 photos (NHM granite and marble are almost all polished slab scans), slate 8, magnetite
- Not started: Europeana (needs EUROPEANA_API_KEY), GeoCASe, more Commons/Smithsonian queries for the weak classes
