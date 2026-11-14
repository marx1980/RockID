# Challenge set C: stones with several photos

Status: rules, pre-registration and tooling written 2026-11-14, before any photo of C was harvested or seen.
Nothing in this file may change after the first harvest for C except the runbook commands; a change to a
rule or to the pre-registration needs a DECISIONS.md entry saying why, and makes C a new set (C2).

## Why it exists

Sets A (189 cases) and B (135) are single photos; only 13 and 10 of their specimens have more than one photo,
so they cannot show whether asking the user for 2 to 3 photos of the same stone helps. C has whole stones
(one physical specimen, 2 to 5 photos each) and is built to answer two questions:

1. Does combining the predictions of 2 to 3 photos of one stone beat a single photo?
2. Does "trained head ranks, nearest-photo similarity decides whether to answer" beat the live k-NN
   verdict on answered-and-right rate without naming more out-of-scope photos?

Practical use: the answer decides whether the app gets a "take 2 more photos" step and whether the head ships.
Expected size is about 60 to 120 live-class stones, so only gains of roughly 6 to 9 points top-1 or more
will be distinguishable from noise (paired SD per stone about 0.35; 95% interval half-width 0.09 at 60
stones, 0.06 at 120). Smaller effects will read as "no clear gain".

## 1. What counts as one stone

- A stone is one physical specimen. Views are separate photos of it: another side, angle, light or distance.
- Pool grouping (deterministic): same taxon, same `specimen_hint`, same collection, where collection is the
  photographer (author, lower case) or, for an institution credited as author, the source name.
  `stone_id = "cs:" + sha256("<taxon>|<specimen_hint>|<collection>")[:12]`.
  - Smithsonian: one catalogue record (`si:<record_ID>`) is one stone.
  - Commons: one filename series by one uploader ("Galena-Joplin-03.jpg", "-04.jpg"). The hint is a filename
    heuristic and over-groups numbered series, so the reviewer must confirm every kept stone by eye.
- A pool group that the reviewer finds to hold more than one specimen is not split: either the views of the
  main specimen are listed (`--views`) or the stone is dropped (`not_same_stone`).
- Views: minimum 2, target 3, maximum 5. Pool shows up to 8 views; freeze keeps the first 5 after
  near-duplicate removal. View order is natural sort of candidate_id (Commons page ids grow with upload time).
- Near-duplicate views (dropped automatically, the earlier view is kept): same sha256, or pHash distance <= 8
  under any rotation or mirror, or DINOv2-small cosine >= 0.95. Calibration on the current reference set
  (4,189 pairs of photos with the same specimen id): cosine median 0.68, 95th percentile 0.87, 99th 0.91;
  12 pairs (0.3%) reach 0.95 and 10 pairs have pHash <= 8 (their cosine ranges 0.885 to 0.977, so pHash
  catches copies that cosine misses). Crops and zooms of one photo that pass both checks are dropped by the
  reviewer (`crop_or_duplicate`).
- A photo that is a copy (sha256 or pHash <= 8) of any reference photo or of any photo in A, B, OOD
  calibration or OOD test is dropped. Cross-set cosine is not checked (reference vectors are not built in this
  step); the photographer, specimen and page rules below cover the same risk.

## 2. Leakage rules

Reference side = `reference.csv` plus every candidate decided `approve_*` or `reserve` on main, any taxon.
(This matters now: the 681 round-11 approvals of new minerals are in decisions.json but not in reference.csv,
because `promote` validates rows against mvp21 and drops other taxa as invalid. They count as reference side.)

A stone is eligible only if none of its photos shares, with any reference-side photo of ANY taxon or with any
row of vault A, B, OOD calibration, OOD test or form hold-out:

- an individual photographer (author not empty and not the institution name),
- a specimen id or specimen hint,
- a source page (URL without query and fragment).

Same photographer across taxa is forbidden too. Reason: a new user has no photos in the reference at all. If
the photographer of a C stone has reference photos of other classes, the nearest photos are that
photographer's own (same backdrop, light, camera: the collection shortcut measured at 0.53 vs 0.35 top-1),
which pulls the ranking to the wrong class and inflates the nearest-photo similarity that question 2 uses as
evidence. Cost: it rules out the two largest Commons mineral photographers (Robert M. Lavinsky, 382 reference
photos; James St. John, 269) and roughly halves the eligible stones in the existing pool.

Institutions credited as author (Smithsonian, NHM, Estonian collections) have no photographer key, so the
photographer rule cannot apply to them. Their stones are flagged `institution=1`, capped (5 per class, at most
50% of live stones) and reported as a separate stratum, because the same museum style is in the reference.

Other pool exclusions: a specimen hint that occurs under two taxa; any view whose title names another live
taxon (`other_taxa_in_title`, e.g. "Fluorite on quartz"); licence-rejected candidates.

After freeze, `merge_round` blocks C's photographers, specimens and pages for every taxon (rows with a
`stone_id`), so later reference rounds cannot leak into C. Always pass the C file to `merge_round` and to
`challenge_b.py` from then on.

## 3. Sources weighed

| option | yield (measured 2026-11-14) | honesty | used |
|---|---|---|---|
| Existing undecided candidates | pool today: 88 stones in 13 extra minerals (nearly all Smithsonian), 1 live stone (slate) | good | yes, as part of the pool |
| Smithsonian deeper harvest | earlier harvests stopped at the cap (calcite, fluorite, quartz, azurite at 39 to 40 photos); 31% of harvested Smithsonian records have 2+ images; yield for live minerals unknown until run | museum style is in the reference: capped and stratified | yes |
| Commons deeper search + `commons-series` (new source: other views of a seed file by the same uploader) | unknown; rocks expected thin | good, new photographers only | yes |
| Carving whole multi-photo components out of the reference | 146 stones if only same-taxon overlap is forbidden, 57 under the cross-taxon photographer rule, at a cost of 936 reference photos (36%); chert would lose 107 of 151 | breaks comparability with every A/B score so far; weak classes get weaker | no |
| NHM London, Europeana | 613 of 634 NHM records and all Europeana records have one photo | - | no |
| Mindat, Flickr, iNaturalist, GSJ | no reuse licence / not built, mixed licences / no rocks / images unreachable | - | no |

## 4. Classes and targets

- Live classes (the 21 of mvp21) come first: target 10 stones per class, maximum 15.
- Extra minerals: only those with >= 10 reference-side photos from >= 2 collections (16 today: almandine,
  apatite, aragonite, barite, beryl, bornite, chalcopyrite, chrysocolla, corundum, epidote, galena, kyanite,
  labradorite, sphalerite, topaz, tourmaline). Target 5, maximum 8. They form the secondary population.
- Pool size per class (review load): 25 stones for live classes, 12 for extras, round-robin over collections.
- Per individual photographer: at most 3 stones per class and 8 overall. Per institution: 5 per class.
- A class is reported on its own only with >= 5 stones. Pooled metrics use every stone.
- Freeze gate: >= 60 live stones in >= 10 live classes. If one extra harvest round (runbook step 9) does
  not reach it, freeze with `--underpowered` at >= 40 live stones; every result is then labelled
  "underpowered (n < 60)". Below 40, do not freeze; report to Marko.

## 5. Tumbled and polished stones

Included, because users photograph them. The reviewer marks the stone's form (`--tumbled`, `--polished`;
default natural); one stone has one form. At most 25% of live stones may be non-natural (trimmed in hash
order at freeze). Faceted gems, jewellery and carvings are not stones (`artwork_or_object`). Results are
reported by form as secondary analyses; the primary metric uses every live stone.

## 6. Pre-registration (frozen now; code: services/model/multi_photo.py)

Fixed before C exists. Anything not listed here is exploratory and cannot replace a primary result
without a new frozen set.

- Vectors: DINOv2-small q8 embeddings from compare-model (same code as the app), L2-normalised.
- Reference: `reference.csv` at the commit recorded in `challenge_c_meta.json` (`reference_commit`).
- Head: `LogisticRegression(C=10, max_iter=400)`, no class or sample weights, on all reference photos and
  classes of that commit (the setting of results/lab/ROUND11.md, chosen before any set was read).
- Populations: primary = stones with `scope=live` whose class is in the head; secondary = extra minerals.
- Views used: the first 3 views of each stone (`PRIMARY_K = 3`, the 2-3 photo request of the app).

H1 (multi-photo, ranking only):
- Primary rule: `mean_prob` = arithmetic mean of the per-photo head probability vectors.
- Primary metric: stone-level top-1, compared with the single-photo baseline on the same views
  (baseline per stone = share of its views whose own top-1 is right; stone-weighted mean).
- Test: paired bootstrap over stones, 10,000 resamples, seed 20261114. H1 is supported if the 95% interval
  of the gain (multi minus single) lies above 0.
- Secondary (reported, not confirmatory): top-3; rules `mean_logprob` (geometric mean, floor 1e-4),
  `max_conf` (view with the highest top probability), `vote` (most top-1 votes, ties by mean probability);
  k = 2 and all views; the same with the live k-NN probabilities; per class (>= 5 stones), per stratum
  (institution or individual) and per form.

H2 (head ranks, similarity gives the evidence for answering):
- Verdict: identified iff combined head top probability >= tau_p and s >= tau_s, where s is the highest cosine
  between any used view and any reference photo of the predicted class.
- Thresholds: grid tau_p 0.30 to 0.90 step 0.05, tau_s 0.50 to 0.90 step 0.02. Allowed pairs name at most 5%
  of `vault/ood_calibration.csv` photos (single photos, at most 2 of 56); among them maximise correct answers
  on 5-fold cross-validation of the reference grouped by split component (`split._components` per taxon;
  fold = int(sha256(taxon + smallest asset_id of the component), 16) mod 5);
  ties go to the higher tau_s, then tau_p. A, B, C and the OOD test are never used to choose thresholds.
  Multi-photo verdicts use the same thresholds, no re-tuning.
- Primary metric: answered-and-right rate U on primary stones (first 3 views, mean_prob), against the live
  k-NN verdict (shipped thresholds, applied to the mean of k-NN probabilities on the same views).
  H2 is supported if the bootstrap 95% interval of the U difference lies above 0 AND the head verdict names
  at most 10% of `vault/ood_test.csv` photos. Also reported: answered rate, wrong-answer rate,
  don't-know rate, the same on single photos.
- C is scored once per pre-registered setting. Re-scoring after a model or reference change is a new
  comparison and is labelled with the new reference commit.

## 7. Freezing and file format

- Vault branch: `challenge_c.csv` and `challenge_c_meta.json` (summary, reference commit, rule constants).
- Columns: the A/B columns `case_id,candidate_id,ground_truth_id,specimen_id,source_name,source_url,media_url,
  author,license` (existing scoring code reads C as single photos), then `stone_id,view,form,institution,scope`.
  `case_id` is `s0001...` in (taxon, stone_id, view) order. One row per photo.
- Main: `data_manifests/candidates/challenge_c_pool.csv` (pool), `challenge_c_review.csv` (one row per photo:
  keep or drop with a reason), and decisions.json gets `reserve` for every frozen photo.
- compare-model embeds `vault/challenge_c.csv` (to `emb/challenge_c`) once it exists; it never scores C.

## 8. Runbook

Roles: a harvest and review agent (Sonnet) runs steps 0 to 8; an Opus agent runs 10 to 12. GitHub REST only.
Dispatch form: `gh api -X POST repos/marx1980/RockID/actions/workflows/<file>/dispatches -f ref=main -f 'inputs[x]=y'`.
Merge every PR with `gh api -X PUT repos/marx1980/RockID/pulls/<n>/merge -f merge_method=squash`.
Retry 503 "Session policy temporarily unavailable" with sleeps. Do not start any other review round until C is
frozen: an undecided C photo approved elsewhere would leak.

0. Setup: `cd /home/claude/rockid && git checkout main && git pull`; vault copies:
   `mkdir -p /tmp/vault && for f in challenge.csv challenge_b.csv ood_calibration.csv ood_test.csv form_holdout.csv; do git show origin/vault:$f > /tmp/vault/$f; done`
   (`git fetch origin vault:refs/remotes/origin/vault` first).
1. Smithsonian, deeper: dispatch `harvest.yml` with `inputs[sources]=smithsonian`, `inputs[per_taxon]=600`,
   `inputs[taxa]=` the 21 live ids plus the 16 extras of section 4 (space-separated). Merge `harvest/run-<id>`.
2. Commons, deeper, live classes only: `inputs[sources]=commons`, `inputs[per_taxon]=400`,
   `inputs[taxa]=` the 21 live ids. Merge.
3. Commons series (needs step 2 on main): `inputs[sources]=commons-series`, taxa = live + extras. Merge.
4. Pool (offline):
   `python -m services.curation.challenge_c pool data_manifests/candidates/candidates.csv data_manifests/candidates/decisions.json data_manifests/reference/reference.csv data_manifests/candidates/challenge_c_review.csv data_manifests/candidates/challenge_c_pool.csv /tmp/vault/challenge.csv /tmp/vault/challenge_b.csv /tmp/vault/ood_calibration.csv /tmp/vault/ood_test.csv /tmp/vault/form_holdout.csv`
   Keep the printed report (eligible and pooled stones per class). Commit the pool on a branch, PR, merge.
5. Sheets: dispatch `challenge-c.yml` with `inputs[step]=sheets`. Clone or fetch `curation/c-sheets-<runid>`
   (files `sheets/c-<taxon>-<n>.jpg`, `index.json`, `missing.json`). One row per stone, `S<n>` on the left,
   views numbered 1 to 8.
6. Review: view each sheet once and write its decision straight after (image requests are limited). Per taxon:
   `python -m services.curation.challenge_c decide <sheets>/index.json data_manifests/candidates/challenge_c_review.csv <taxon> --keep "1-3,5" --views "2:1-3;5:1,3" --reasons "4:not_same_stone;6:other_mineral_dominant" --tumbled "7" --polished "" --missing <sheets>/missing.json`
   - `--keep`: stones kept; `--views`: which views of a kept stone stay (default all); stones not kept get
     `--default` (`not_same_stone_or_unusable`) or their `--reasons` entry. `decide` refuses a kept stone with
     fewer than 2 usable views and refuses candidates already in the review file.
   - Keep a stone only if: every kept view shows the same piece (outline, colour pattern, crystals match); it
     is a hand specimen, not an outcrop, scene, building or display of several specimens; the named taxon is
     plausible and dominant; no other mineral dominates.
   - Drop a view that is a crop or zoom of another view (`crop_or_duplicate`), a label card or catalogue
     sheet (`not_a_specimen_photo`), a microscope image (`microscope_image`) or another specimen.
   - Stone reasons: `not_same_stone`, `scene_not_specimen`, `outcrop_not_specimen`, `artwork_or_object`,
     `display_multiple_specimens`, `other_mineral_dominant`, `ambiguous_identity`, `wrong_subject`.
   - Do not judge identity beyond plausibility; the source label is the truth. Doubt means `ambiguous_identity`.
7. Commit `challenge_c_review.csv` (PR, merge). Then dispatch `challenge-c.yml` with `inputs[step]=check` and
   fetch `results/challenge_c_check.json` from `check/challenge-c-<runid>`.
8. Yield check (offline):
   `python -m services.curation.challenge_c draft data_manifests/candidates/challenge_c_pool.csv data_manifests/candidates/challenge_c_review.csv /tmp/c_draft.csv && python -m services.curation.challenge_c freeze /tmp/c_draft.csv <check.json> data_manifests/candidates/decisions.json /tmp/challenge_c.csv --dry-run`
   Report `live_stones`, `live_classes`, `per_class`, `freeze_ok` to the Opus agent and stop.
9. Only if `freeze_ok` is false: one more round with `inputs[sources]=commons-categories commons-series`
   (taxa = live classes short of 5 stones), then steps 4 to 8 again (pool keeps reviewed rows; sheets skip
   reviewed stones). No further rounds after that: apply the fallback of section 4.
10. Freeze (Opus): rerun step 8 without `--dry-run` (add `--underpowered` only under the section 4 fallback)
    with `--reference-commit $(git rev-parse HEAD)`. This writes `/tmp/challenge_c.csv`,
    `/tmp/challenge_c_meta.json` and `reserve` decisions. PR and merge decisions.json on main; add both files
    to the vault branch (worktree on `origin/vault`, commit, push as for B).
11. Embed: dispatch `compare-model.yml` with `inputs[tag]=dinov2-small-c` (defaults); the branch
    `compare/dinov2-small-c-<runid>` holds `emb/reference.*`, `emb/challenge_c.*`, `emb/ood_cal.*`, `emb/ood_test.*`.
12. Score (Opus) once, with `services/model/multi_photo.py`: fit the head on `emb/reference` (labels from
    item `t`), per-photo probabilities for C, `stones()` + `summary()` for H1, `choose_thresholds()` on OOD
    calibration and reference grouped CV for H2. Write `results/challenge_c/RESULT.md` with every primary and
    secondary number listed in section 6, the reference commit and the meta file.

## 9. Risks

- Yield for live classes is the main risk. Existing candidates give 1 live stone. Smithsonian is likely to
  supply live minerals (earlier harvests hit their cap) but is capped at 5 per class and 50% overall; rocks
  are thin there (chert 2, quartzite 9, slate 7 harvested photos) and on Commons multi-view rock series by new
  photographers are rare. Expect most rock classes below 5 stones (pooled only, not reported per class).
- Commons specimen hints over-group; reviewer confirmation is the only guard against two specimens in a stone.
- The cross-taxon photographer rule removes the most prolific Commons mineral photographers; C is therefore
  more museum-heavy for minerals than ideal. The stratified report shows whether that changes the reading.
- Same-photographer stones (up to 3 per class) are correlated; the bootstrap resamples stones, not
  photographers, so its interval is slightly too narrow.
