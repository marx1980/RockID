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
