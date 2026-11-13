# Challenge Vault (benchmark ground truth)

Label-bearing challenge manifest. Never merge into main; the identifier, API image and CI do not read this branch.
Photos are disjoint from the reference set by photographer, specimen and source page (services/curation/split.py).

`challenge_b.csv` is a second challenge set (round 9): whole held-out photographers of the weak classes, disjoint from the reference set and from `challenge.csv` by photographer, specimen and source page (services/curation/challenge_b.py).

Leakage check (round 10): pHash comparison of both sets against the reference set found 6 visual duplicates (distance 0, Europeana records of the same photo) and 1 same-specimen case; these 7 cases were removed (A: c0045; B: b0031, b0035, b0036, b0037, b0038, b0109). Near matches at distance 6 to 8 that are different photos (c0021, c0057, b0042, b0043) were kept.

OOD sets (round 10): `ood_calibration.csv` and `ood_test.csv` hold photos of things that are not in the taxonomy (other minerals, other rocks, man-made material, other natural objects), reviewed by eye, truth `UNKNOWN`: the right answer is to abstain. Whole photographers go to one side only (services/curation/ood_set.py). Abstention thresholds may be tuned on `ood_calibration.csv`; `ood_test.csv` is frozen and scored once per chosen setting. OOD photos never enter the reference set.
