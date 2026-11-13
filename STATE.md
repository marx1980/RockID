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
- pHash leakage between reference and challenge checked in round 10 (7 cases removed)

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
3. P5: choose thresholds on the OOD calibration set (after H-03), follow-up answers fed back into ranking. Leakage check and OOD sets are done (round 10).

## P3b so far
- NHM London harvester (services/ingestion/sources/nhm.py), review rounds (contact sheets with prefix, merge_round), tagged re-score
- 634 NHM candidates reviewed visually: 49 approved and promoted, 582 rejected (443 polished slab scans, 120 surplus sandstone)
- Reference set 692 photos; v2 re-score neutral (results/BASELINE_v2.md); live app still on model v1
- Still thin: marble 2, biotite 3, granite 8 photos (NHM granite and marble are almost all polished slab scans), slate 8, magnetite
- Europeana source built and run (1,974 candidates; 294 auto-rejected by provider and title rules; 1,331 reviewed visually in round 3, 450 approved and promoted; Vienna, Paris and Naturalis thumbnails unreachable, 350 left unreviewed)
- Reference set 1,142 photos; v3 re-score (results/BASELINE_v3.md): shortlist top-1 0.511, top-3 0.821, mineral vs rock 0.900; live app still on model v1
- Now: marble 3, slate 11, biotite 25, magnetite 42 photos; most new photos come from one Estonian collection (black or white backdrop, scale bar)
- Not started: GeoCASe, more Commons/Smithsonian queries for the weak classes, Europeana thumbnail fallback, pHash check of reference against challenge

## Form flag (tumbled / polished)
- `form` column in reference.csv (natural, tumbled, polished) and forms.json; polished covers sawn or polished slabs, cabochons, spheres; faceted gems stay out
- Polished reinstated (359 from NHM/Europeana, 60 per taxon and source cap); round 4 reviewed 315 Commons "tumbled" candidates, 75 approved (60 tumbled, 8 polished, rest natural)
- Reference set 1,577 photos: 1,149 natural, 368 polished, 60 tumbled
- App votes the form of the photo from all references; if form_p >= 0.6 and the form has >= 30 references, it ranks taxa among that form only; result shows a Tumbled or Polished chip
- Model v4 live (results/BASELINE_v4.md, FORMS_v4.md); natural challenge top-1 0.516, top-3 0.805, mineral vs rock 0.895
- Polished hold-out (vault/form_holdout.csv, 252 capped-out NHM photos of marble, granite, limestone): form detected 0.98, top-1 0.67, top-3 0.97. Weak test: one collection, three taxa
- Tumbled: only 60 references (36 chert from one collector, 23 malachite, 31 quartz overlap by taxon), no hold-out; LOSO form accuracy 0.85
- Thresholds 0.6 and 30 are uncalibrated; challenge set is natural-only; commons-polished harvest not run; tumbled sources scarce

## Round 6: Wikipedia-article images
- `wikipedia` harvest source (services/ingestion/sources/wikipedia.py, packages/taxonomy/wikipedia_articles.csv, 21 taxa): article image lists, licence from Commons
- 734 candidates reviewed, 149 approved and promoted; reference set 1,834 photos
- Score with same model (results/compare/dinov2-small-v6): challenge top-1 0.495, top-3 0.800; Commons 0.39 / 0.71; shipped later as model v9 (see below)
- Rock articles yield little (outcrops, structures); weak rock classes still need specimen photos from other sources
- Round 7: ~150 subtype articles; 141 approved; 1,975 reference photos; challenge top-1 0.489, top-3 0.795, Commons 0.37 / 0.71 (results/compare/dinov2-small-v7); not shipped
- Least natural coverage now: marble 11 photos, slate 22, granite 54 (28 specimens), chert 60 (28), magnetite 58 (22)

## Rounds 8 and 9 and challenge set B
- Round 8: Smithsonian re-harvest, 111 approved. Round 9: `commons-categories` source (packages/taxonomy/commons_categories.csv, services/ingestion/sources/commons_categories.py), 1,933 reviewed, 661 approved; sheet caps `--per-author 10 --per-taxon 200`
- Challenge set B (vault branch `challenge_b.csv`, 141 cases): whole held-out photographers, weak classes (marble 22, chert 11, biotite 8, magnetite 8, muscovite 23, granite 19, gneiss 13, limestone 13, sandstone 13, basalt 9, quartzite 2, slate 0); built by services/curation/challenge_b.py
- Reference now 2,592 photos (marble 241, granite 238, limestone 244, chert 151, sandstone 146, basalt 138, gneiss 126, muscovite 97, magnetite 97, quartzite 95, biotite 61, slate 35)
- v9 score (results/compare/dinov2-small-v9): A top-1 0.474 / top-3 0.774; B 0.454 / 0.674 (v7 reference on the same B cases 0.355 / 0.617); other-collections-only 0.355; not shipped, v4 live
- Known gaps: slate (35 photos, no B cases), quartzite (2 B cases), challenge A still 74% Smithsonian; B is Commons only so it does not test museum-style photos

## Round 10: v9 shipped, leakage check, OOD sets
- v9 shipped (build-model run 43444506217, PR #73): 2,592 reference photos, live in the app.
- Leakage check (services/curation/challenge_leakage.py, workflow leakage-check): pHash of both challenge sets against the reference set found 6 visual duplicates and 1 same-specimen case; 7 cases removed. Challenge A is now 189 cases, B 135. Scores on the cleaned sets: A top-1 0.471 / top-3 0.772 (v7 0.492 / 0.794); B 0.437 / 0.659 (v7 reference 0.333 / 0.600).
- OOD sets (vault `ood_calibration.csv`, `ood_test.csv`, 56 + 56 cases, truth UNKNOWN): 440 Commons candidates from `packages/taxonomy/ood_categories.csv` reviewed by eye, 112 approved (other minerals 48, other rocks 20, man-made 25, other natural 19). Rejected: outcrops, scenes, diagrams, statues, displays with many specimens, and coal, meteorites and petrified wood (identity too close to rock). Split by whole photographer (services/curation/ood_set.py). Thresholds may be tuned on the calibration set only; the frozen test is scored once per chosen setting.
- v9 on OOD (results/compare/dinov2-small-v9-ood): with the shipped thresholds (floor 0.65, p 0.4, margin 0.1) 11% of calibration OOD photos are wrongly named (7% on the frozen test, 4 of 56), worst for man-made material and other rocks. The sweep (OOD_SWEEP.md) shows stricter settings (p 0.7) drop that to 2% but cut answered coverage on reference photos from 34% to 13%. Choice of setting waits for H-03.
- Not done: P5 threshold choice, follow-up prompts, OOD photos from phone cameras.

## Round 10b: new sources (USGS, MineralImage5k)
- USGS Multimedia Gallery (public domain): `usgs` harvest source (services/ingestion/sources/usgs.py). 59 candidates, 46 flagged as generic renderings that look machine-generated; only 13 look like real photos and about 6 are rocks (granite, marble, sandstone, gneiss). Not reviewed or merged: too small to justify a round. Rejected for the same purpose: Pixabay (its terms bar ML training), Vecteezy and Freepik (attribution-only licences, stock cutouts and vectors), Flickr Commons (mostly historical drawings).
- MineralImage5k (Fersman Museum photos, Hugging Face copy Nech-C/mineralimage5K-98, labelled MIT on the packaging only): private use. `private-source` workflow downloads it on the runner and commits only vectors and labels (data_manifests/private/, no images or URLs). 98 mineral classes, no biotite, no rocks. As reference (1,186 photos, 11 of our taxa, capped at 120 each) v9 gets worse: A top-1 0.471 to 0.429, B 0.437 to 0.407 (results/compare/dinov2-small-v9-mi5k); k-feldspar and gypsum improve, muscovite, chert, gneiss and limestone fall. Not used as reference.
- As OOD: 78 other-mineral species, 468 photos split by species into calibration and test (234 each). v9 with shipped thresholds wrongly names 8.5% of calibration and 11% of test photos (26 of 234).
- Kaggle 7-class mineral set (biotite, bornite, chrysocolla, malachite, muscovite, pyrite, quartz): not fetched; needs a Kaggle token or a zip from Marko.

## Labelling your own photos (round 10c)
- App: result screen has Label (pick one of the 21 types, or Other with a name); labels and 1024 px photos are stored in the phone's IndexedDB; Settings > Export shares or downloads `rockid-labels-<date>.json`.
- Import: `python -m services.curation.own_photos <export.json>` re-encodes the photos (no metadata), adds taxon-labelled ones to the reference set (source "Own photos (Marko)", licence "Own work", one specimen per taxon per day) and keeps "Other" photos as OOD cases in data_manifests/own_photos/ood.csv. Photos are committed to the repo, so they are public.
- Own photos are never in the frozen challenge or OOD test sets.

## Model comparison and shortcut check (results/compare/COMPARISON.md)
- compare-model workflow: any HF ONNX DINOv2 or SigLIP model, or a centre-masked probe; writes results/compare/<tag>/ and never touches the app
- services/model/shortcut.py: reference k-NN with own collection removed vs random control; challenge split by collection
- DINOv2-small stays live; dinov2-base and SigLIP2-base are worse on photos from new photographers
- Collection shortcut confirmed: own-collection removal 0.53 → 0.35 top-1 (random control 0.53); realistic phone-photo expectation about 0.35-0.40 top-1, 0.78 top-3
- Known gap: calibration on leave-one-specimen-out overstates confidence; challenge set is 74% Smithsonian

## Round 5 (locality harvest)
- commons-places harvest source and packages/taxonomy/localities.csv; 110 approved of 941 reviewed; reference set 1,687 photos (1,149 + 110 natural/polished mix, 60 tumbled)
- v5 re-score neutral (results/BASELINE_v5.md); live app still on model v4
