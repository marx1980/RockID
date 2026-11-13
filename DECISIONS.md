# Decisions

## 2026-11-13 Challenge Vault isolation by network, not only credentials
Reason: a missing password is one config mistake away from a leak. Rejected: shared default network.

## 2026-11-13 Taxonomy MVP21 with stable IDs and K-feldspar
Reason: feldspar dominates granite/gneiss; IDs decouple names from data. Rejected: keeping MVP20 names as keys.

## 2026-11-13 Specimen-balanced k-NN before any fine-tuning
Reason: small, uneven reference sets; one vote per specimen resists photo-count bias. Rejected: training a classifier head first.

## 2026-11-13 P1: harvest in GitHub Actions
Reason: the dev workspace blocks outbound hosts other than package registries and GitHub. Rejected: asking for an allowlist change first.

## 2026-11-13 P1: first sources are Smithsonian NMNH Mineral Sciences and Wikimedia Commons
Reason: Smithsonian media flagged CC0 come with catalogue records (reliable specimen IDs); Commons adds field/collector-style photos. Rejected for now: Mindat (photographer copyright, no general reuse licence), Flickr (mixed licences, noisy), iNaturalist (geology coverage thin).

## 2026-11-13 P1: licence policy (APPROVED by Marko 2026-11-13)
- CC0 / public domain → allowed_train
- CC BY, CC BY-SA → allowed_reference_only (used for nearest-neighbour matching with attribution, not for training weights)
- NC, ND, unknown → rejected
Reason: conservative default; whether CC BY-SA permits training is not settled. Changing it means editing `licence_policy.csv` and noting it here.

## 2026-11-13 P1: specimen ID from source when available, otherwise a low-confidence hint
Reason: specimen identity drives leakage checks and vote balancing. Commons hints group photo series by filename and must be reviewed; over-grouping is the safe error.

## 2026-11-13 P1: images stored by sha256 outside git
Reason: repo size and per-image licence obligations. Storage backend decided in P2.

## 2026-11-13 P1 gate summary
G-01 PASS; G-02 PASS provisional (all 21 taxa ≥ 9 specimen hints before review); H-01 pending. Weakest classes before review: magnetite (9), chert (10), granite (10).

## 2026-11-13 P2: review page on GitHub Pages, not a claude.ai artifact
Reason: artifact pages cannot load remote images, and the photos live on Smithsonian and Wikimedia hosts. Pages (repo is public) has no such limit. Rejected: embedding 1,500 thumbnails as data URIs (size limit, needs a download step), a local review app (phone-first).

## 2026-11-13 P2: decisions in their own file, saved by the page through the GitHub contents API
Reason: no backend; a harvest re-run must never overwrite review work; decisions.json merges cleanly (sorted keys, one line each). The token is a fine-grained PAT limited to this repo (Contents read/write), kept in the browser's localStorage. Without a token decisions stay in the browser and can be copied out.

## 2026-11-13 P2: images are not stored; the manifest keeps media_url and sha256
Reason: CC BY / CC BY-SA photos should not be redistributed by us (release assets and workflow artifacts are public for a public repo), and the corpus is small enough to re-fetch. P3 re-downloads from media_url and must verify sha256; a mismatch flags the asset. Risk: a source changes or removes an image. Rejected: GitHub Release assets, workflow artifacts, a private bucket (cost and setup for no current need).

## 2026-11-13 P2: near-duplicate auto-quarantine at pHash distance 4 (uncalibrated)
Reason: the review threshold of 8 would drop genuinely different photos of similar-looking specimens on plain backgrounds. Quarantined rows go to quarantine.csv with the matched asset for later manual review. To be calibrated on the real corpus in P4.

## 2026-11-13 P2: manifest schema change (media_url added)
Manifest columns and the reference `assets` table gained `media_url`; `assets` gained `quarantine_reason`. No deployed database exists yet, so 001_init.sql was edited in place.

## 2026-11-13 Agent curation replaces manual review
Marko asked for agents, not him, to review candidates. A visual-review agent (Claude reading numbered contact sheets built in Actions) decided every one of 1,436 candidates: 839 approved, 597 rejected with a reason code (`data_manifests/candidates/agent_review.csv`). Rejections: other mineral dominant, cut gems and polished slabs, outcrops and scenes, artworks and objects, displays, microscope images, ambiguous identity. The phone review page stays as an optional check of the agent's calls. Rejected: per-image API review (needs a key, costs per image; can be added later).

## 2026-11-13 Polished, cut and tumbled stones excluded for now
Natural specimens only in this pass. Real users often photograph polished malachite, tumbled stones and granite countertops, so a later suite may need them. Open product question for Marko.

## 2026-11-13 Reference/challenge split by independent groups
Within each taxon, photos are joined into groups that share a photographer, specimen or source page; whole groups go to one side (`services/curation/split.py`), ~25% to challenge, never leaving fewer than 3 reference specimens. Museum credits are not treated as photographers. Result: 645 reference, 190 challenge; no challenge cases for chert (one photographer group) and marble (2 usable specimens).

## 2026-11-13 Challenge manifest on an orphan `vault` branch
Main carries `reserve` for challenge photos (excluded from reference and from the review page); the label-bearing manifest lives on the `vault` branch, which the app, API image and CI never check out. The repo is public, so this protects the pipeline from consuming test labels, not against a person reading them. Upgrade path: a private repo or the Challenge Vault database.

## 2026-11-13 Camera-first identify app
`app/` opens on the rear camera (framing guide, shutter, Photos, Collection), falls back to Take photo / Upload. Result: best match, might also be, a follow-up check per confusion group, properties, features; collection on the device. With no model installed it says Not identified; a Demo switch in settings shows the layout with clearly marked fake results. Property and follow-up data live in `packages/taxonomy/properties.csv` and `followups.csv` (standard reference values, to be checked by the Domain Curator).

## 2026-11-13 P3: DINOv2-small in the browser, specimen-balanced k-NN, no training
Model `onnx-community/dinov2-small`, int8 (`q8`, ~24 MB, Apache-2.0 weights), run by transformers.js 3.8.1 both in the build job (Node) and on the phone, from the same `app/model/core.mjs`, so reference and query embeddings come from identical code. Embedding: L2(concat(L2(CLS), L2(mean patch tokens))), 768-d. Reference vectors (~2 MB) ship with the app; weights download from Hugging Face on first identify and are cached by the browser. Rejected for now: a server (no hosting yet), fine-tuning (too little data), SigLIP2 (larger, no measured gain yet).

## 2026-11-13 P3: thresholds calibrated on reference only, challenge scored once
`services/model/evaluate.py` sweeps decision thresholds on reference leave-one-specimen-out (target: 80% selective accuracy, maximise coverage; OOD floor = 5th percentile of correct-match similarity), then scores the challenge set once. Challenge images are embedded from a CSV holding only case ids and URLs; predictions are written before labels are read. JS and Python decision code are checked against each other in tests.

## 2026-11-13 Branch deletion through a workflow
This session cannot delete remote branches (API and git push --delete are refused), so `cleanup-branches` deletes temporary branches with the workflow token.

## 2026-11-13 NHM London source (P3b)
Data Portal CKAN API, no key. Only ~4,800 mineralogy records have photos, nearly all CC BY 4.0 (reference-only under our policy) with reliable catalogue numbers as specimen IDs. The portal cannot filter by name substring, so the harvester fetches all imaged records once (10 polite calls) and matches by name locally, rejecting containers and host-rock mentions ("granite" only as the host of a wolframite vein, "quartz-porphyry"). Media URL is the plain `data.nhm.ac.uk/media/<asset>` (the IIIF `!1024,1024` form returns 400 for images smaller than 1024 px). Mineral coverage is negligible (a handful of quartz, calcite, pyrite); the volume is ornamental and building stone.

## 2026-11-13 NHM review: polished slab scans rejected, sandstone capped
Of 631 photos, 49 approved. 443 were flat-bed scans of sawn/polished ornamental slabs with a scale bar (all of marble, nearly all of granite and limestone), rejected under the standing rule that polished or cut stone is out (reason `polished_slab_scan`, so they can be flipped later if Marko includes polished stone). Sandstone is natural rock on one black lab backdrop with a colour checker in every photo; 30 kept, 120 rejected as `surplus_same_collection` so one backdrop cannot dominate the class. Kept: 30 sandstone, 8 limestone, 5 granite, 4 calcite, 1 basalt, 1 slate.

## 2026-11-13 Later review rounds merge without re-splitting
The challenge set is frozen once scored. `services/curation/merge_round.py` adds new approvals to the reference side only, and turns an approval into a reject if it shares a photographer, specimen or source page with a challenge case of the same taxon (none did). Contact sheets take a round prefix and skip already-reviewed candidates. Institution-level hold-out was not adopted: it would have removed NHM from the reference side of the classes it is meant to help. A second challenge set from a different institution stays an option for a later phase.

## 2026-11-13 NHM re-score: neutral, v1 model stays live
Rebuilt with 692 reference photos and scored on the same challenge set as a labelled second evaluation (BASELINE_v2.md; v1 files untouched). Shortlist top-1 0.474 (v1 0.479), top-3 0.784 (0.800), mineral vs rock 0.932 (0.926); committed coverage 0.163 at 0.742 (0.153 at 0.759). All differences are 1 to 3 cases of 190, i.e. noise. Granite committed recall stays 0.00 (5 cases). No model change was shipped on this evidence; the new data would be kept for the next comparison.

## 2026-11-13 Europeana source and review (P3b)
Search API with the key in `EUROPEANA_API_KEY`; open-reuse images only, titles must name the taxon and not a place, building or host rock, and non-natural-history providers are dropped by name. Rights URIs map to the same licence policy; the record id is a low-confidence specimen hint. Of 1,331 photos reviewed visually, 450 were approved: natural hand specimens with the taxon visible. Rejected with reason codes: thin sections (all of the limestone and sandstone microscope scans), polished or cut slabs, label cards and non-rock photos, other minerals dominating, taxon not visible. Marble stayed at 1 approval because the Estonian marble is polished tiles.

## 2026-11-13 Europeana re-score: AMBER, v1 model stays live
Rebuilt with 1,142 reference photos and scored a third time on the unchanged challenge set (BASELINE_v3.md). Shortlist top-1 0.511 (v1 0.479, v2 0.474), top-3 0.821 (0.800, 0.784), but mineral vs rock fell to 0.900 (0.932) and ECE rose to 0.258 (0.204). Gains are 6 to 7 cases of 190, which is at the edge of noise. Most added photos come from one collection with a uniform backdrop, so a domain shortcut cannot be ruled out; no thresholds or model were changed, and the app stays on v1 until a larger-model comparison on this data.

## 2026-11-13 Form flag for tumbled and polished stones
Marko wants tumbled and polished stones identified too. Added a `form` value per reference photo (natural, tumbled, polished; blank means natural). The app votes the photo's form from all references (specimen-balanced, temperature 0.05); when the vote is at least 0.6 and that form has at least 30 references it ranks taxa among that form's references only, otherwise it uses all. The result shows the form as a chip. Rejected: a separate model per form (too little tumbled data), and a form selector in the UI (extra step, detection is 0.85 to 0.98).

## 2026-11-13 Polished stone reinstated (policy change)
The earlier rule that polished or cut stone is out is reversed for polished slabs, cabochons and spheres: reasons `polished_slab_scan` and `polished_or_cut` flipped to `polished` unless the photo shares a photographer, specimen or source page with a challenge case. Faceted gems stay rejected. Cap of 60 per taxon and source (sha1 order); the 252 capped-out photos (marble 89, granite 83, limestone 80, all NHM) became `form_holdout.csv` on the vault branch.

## 2026-11-13 Round 4 and model v4 ship
Round 4: 315 Commons "tumbled <name>" candidates, 75 approved. Rejected: outcrops, waterfalls, documents, assortments, jewellery, faceted gems, other minerals, and tumbled blue-black stones labelled limestone and unakite labelled granite (identity unclear). Chert approvals are mostly jasper-like tumbled stones from one collector. v4 is shipped to the app because the form feature needs the new references, despite the AMBER caveat on v3 (shortcut risk, mineral vs rock 0.900 to 0.895, ECE). Natural challenge accuracy is neutral to v1 (top-1 0.516 vs 0.479, top-3 0.805 vs 0.800). Revert by restoring app/model from main before this PR if real-rock tests (H-03) look worse.

## 2026-11-13 Larger models compared: DINOv2-small stays
Same references (v4), challenge and polished hold-out, through the new compare-model workflow (results/compare/COMPARISON.md). dinov2-base q8: challenge top-1 0.447, top-3 0.726; SigLIP2-base q8: 0.379, 0.668; live dinov2-small: 0.516, 0.805. On the 49 challenge cases from new photographers small leads on top-3 by 10+ cases. Rejected: switching to either larger model (worse on new photographers, about 4x the download). Not tried: fp32 weights, dinov2-large, fine-tuning.

## 2026-11-13 Collection shortcut confirmed; accuracy figures restated
For every model, k-NN over reference photos loses about a third of its top-1 accuracy when the query's own collection is removed (live model 0.53 to 0.35), while a size-matched random removal changes nothing (0.53). 141 of 190 challenge cases are Smithsonian photos and Smithsonian also supplies reference photos, so the challenge top-1 (0.52) overstates new-photo accuracy; the Commons cases (new photographers) give 0.39 top-1 and 0.78 top-3. The calibrated "identified" threshold (target 0.8 selective accuracy) was set on leave-one-specimen-out and is likely overconfident on phone photos. A centre-masked probe keeps 0.26 challenge top-1, so the surround of the photo carries a lot; it cannot separate backdrop from specimen edges. Proposed fixes, not yet done: calibrate on leave-one-collection-out, crop to the specimen before embedding, a challenge set built from new collections only (including tumbled and polished), and per-collection balance in the k-NN vote.

## 2026-11-13 Locality harvest (round 5): neutral, v4 stays live
Wikipedia searches (text only) gave locality lists per rock type; they became `packages/taxonomy/localities.csv` and a `commons-places` harvest source (Commons query "<place> <rock>", 12 per place). 1,803 candidates; capped at 5 per photographer and taxon before review (469 rejected as surplus_same_collection); 941 reviewed visually, 110 approved (12%, 6% of the raw harvest): the rest were landscapes, buildings, statues, maps, stamps, outcrops. Reference set 1,687 photos. Re-score v5: challenge top-1 0.526, top-3 0.800 (v4 0.516, 0.805); Commons cases 0.41 / 0.76 (0.39 / 0.78); reference top-1 with own collection removed 0.339 (0.352); nearest specimen from same collection 0.60 (0.64). All differences are noise-sized, so the app was not updated. Locality queries are a poor yield on Commons: most new photographers contributed one scenic photo. More targeted sources (mineral and rock collectors on Flickr/iNaturalist under open licences, geology department collections) or the user's own labelled phone photos would add more.

## 2026-11-13 Wikipedia-article images (round 6): neutral, v4 stays live
Marko pointed to the images used on mineral and rock articles (for example Biotite) as a source of both crystal and rock photos. A `wikipedia` harvest source reads each article's image list, takes licence and author from Commons and drops non-free files; 21 taxa gave 734 candidates. Visual review approved 149 (most gypsum, quartz, malachite, azurite, calcite, fluorite, pyrite) and rejected 233: diagrams, thin sections, outcrops, carvings, buildings and molecular models. Rock articles gave little (basalt 2, slate 1, sandstone 1, chert 3) because their images are mostly outcrops and structures; mineral articles gave a lot. Six approvals shared a photographer with a challenge case and two had a specimen id spanning two taxa, so they were rejected. Reference set is 1,834 photos. The compare run with the same model gives challenge top-1 0.495, top-3 0.800 against v4 0.516 and 0.805; Commons cases 0.39 and 0.71 against 0.39 and 0.78 (49 cases, within noise). Nothing was shipped. Reason: the new photos add specimens but mostly to classes that were already strong, and curated article photos carry another backdrop style that the weak classes do not gain from.

## 2026-11-13 Wikipedia subtype articles (round 7): neutral, v4 stays live
The Wikipedia source now reads about 150 hand-picked subtype and variety articles (Flint, Jasper, Agate, Amethyst, Amazonite, Chalk, Travertine, Carrara marble and so on) for the 21 taxa, with the per-taxon limit raised to 600. 502 new candidates were reviewed, 141 approved (62 quartz, 20 chert, 12 k-feldspar, 13 gypsum, 9 limestone) and 361 rejected. Rock classes again gave almost nothing (marble 2, slate 4, sandstone 2, quartzite 1): marble articles are buildings and statues. Reference set 1,975 photos. Score with the same model: challenge top-1 0.489, top-3 0.795 against v4 0.516 and 0.805; Commons cases 0.37 and 0.71 against 0.39 and 0.78. Nothing shipped. Reading: more Wikipedia photos of already-strong mineral classes do not help; the gap is natural specimen photos of marble, slate, chert and granite from other sources.
