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
