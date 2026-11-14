# Round 11 lab: why more classes hurt, and what survives (2026-11-14)

Offline, on stored vectors only (`python3 services/model/lab.py <dir with reference + private vectors>`). Not the frozen challenge sets.

| test | k-NN now top-1 / top-3 | linear head top-1 / top-3 |
|---|---|---|
| A1 web photos of 5 live classes (Kaggle, unseen source, 412), reference = live 21 classes | 0.430 / 0.762 | 0.597 / 0.905 |
| A2 same, reference + 76 museum-only classes | 0.357 / 0.590 | 0.558 / 0.840 |
| C1 photos of 11 classes, multi-source reference (leave-one-specimen-out) | 0.512 / 0.782 | not run |
| C2 those 11 classes known only from museum photos | 0.323 / 0.577 | 0.309 / 0.600 |
| C3 same, plus 76 museum-only classes | 0.187 / 0.371 | 0.232 / 0.432 |
| B2 museum photos of live classes, reference includes 76 museum classes | 0.068 / 0.128 | 0.099 / 0.193 |

Readings:
- There is no "don't know" entry in the ranking; top-1 and top-3 ignore the verdict. On challenge A the 99-class run lost 32 cases and gained 2; lost cases went to named new minerals, only 1 of 32 in the same look-alike group.
- Neighbour pool size is not the cause (k=50 and whole-set search agree).
- A trained linear head on the same frozen vectors beats the neighbour vote on unseen-source photos and keeps most of it with 97 classes.
- A class known from one museum only is recognised poorly from other photos (C2, C3) and pulls same-style photos away from the right class (B2). Removing collection directions helps little.
- Limits: A covers 5 classes; head untuned (C=10); frozen challenge sets not scored with the head.

## Trained classifier on the frozen challenge sets (2026-11-14)

`services/model/head_frozen.py`, on vectors stored by compare runs 43519706634 (23 classes) and 43516330744 (99 classes). Logistic regression on the frozen DINOv2 vectors, C=10 fixed before these sets were read (same setting as lab.py); other C values shown for information only.

| reference | method | A top-1 / top-3 | B top-1 / top-3 |
|---|---|---|---|
| 21 + Kaggle (23 classes, 3,220 photos) | k-NN now | 0.455 / 0.762 | 0.437 / 0.637 |
| same | head C=10 | 0.582 / 0.788 | 0.593 / 0.756 |
| same | head C=1 / C=100 | 0.519 / 0.767, 0.534 / 0.762 | 0.570 / 0.756, 0.504 / 0.733 |
| 21 + Kaggle + 76 museum (99 classes, 9,451 photos) | k-NN now | 0.312 / 0.534 | 0.311 / 0.481 |
| same | head C=10 | 0.471 / 0.741 | 0.504 / 0.667 |

Live v9 (k-NN, 21 classes): A 0.474 / 0.774, B 0.454.
Not done: form (polished/tumbled) handling with a head, confidence calibration and the don't-know verdict, per-class tests for new classes.
