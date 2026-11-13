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
