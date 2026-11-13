# Model comparison and collection shortcut check (2026-11-13)

Same reference set (1,577 photos, v4), same challenge set (190), same polished hold-out (252). Runs: compare-model 43407151421 (dinov2-base), 43407156513 (siglip2-base), 43407161321 (backdrop probe); dinov2-small is build-model 43401305938.

| model | challenge top-1 / top-3 | Commons cases (49) | Smithsonian cases (141) | mineral vs rock | reference top-1: other specimens → other collections | nearest specimen same collection (chance 0.16) | polished hold-out form / top-1 / top-3 |
|---|---|---|---|---|---|---|---|
| DINOv2-small q8 (live, v4) | 0.516 / 0.805 | 0.39 / 0.78 | 0.56 / 0.82 | 0.895 | 0.53 → 0.35 (random 0.53) | 0.64 | 0.98 / 0.67 / 0.97 |
| DINOv2-base q8 | 0.447 / 0.726 | 0.31 / 0.57 | 0.50 / 0.78 | 0.942 | 0.59 → 0.35 (random 0.58) | 0.67 | 0.96 / 0.68 / 0.98 |
| SigLIP2-base q8 (vision) | 0.379 / 0.668 | 0.24 / 0.55 | 0.43 / 0.71 | 0.874 | 0.56 → 0.33 (random 0.56) | 0.79 | 0.98 / 0.82 / 0.99 |
| DINOv2-small, centre 60% grey | 0.263 / 0.526 | 0.27 / 0.47 | 0.26 / 0.55 | 0.789 | 0.42 → 0.20 (random 0.42) | 0.75 | 0.98 / 0.66 / 0.98 |

Commons challenge cases come from photographers absent from the reference set; Smithsonian cases share the institution (not the specimen or photographer) with 245 reference photos. Committed-answer coverage is 0 for dinov2-base and siglip2-base because their calibrated similarity floor rejects every challenge photo; the shortlist columns are unaffected.

Readings
- DINOv2-small stays: it is best on photos from new photographers (Commons 0.39 / 0.78; dinov2-base 0.31 / 0.57, SigLIP2 0.24 / 0.55) and it is the smallest download. With 49 cases the top-1 gap is 4 cases (noise-level) but the top-3 gap is 10 or more. dinov2-base is better on reference photos when the collection is already known (0.59 vs 0.53) and on mineral vs rock (0.942), but the gain disappears once the collection is removed (0.35 for both).
- Collection shortcut: for every model, removing the query's own collection drops top-1 by about a third (0.53 → 0.35 for the live model) while removing as many photos at random does not (0.53). Two thirds of nearest specimens come from the query's own collection against 16% by chance. Reference leave-one-specimen-out and the Smithsonian-heavy challenge set therefore overstate accuracy on new photos; 0.35 to 0.40 top-1 and about 0.78 top-3 is the realistic expectation for phone photos.
- Backdrop probe: with the centre 60% of each photo grey, the live model still ranks the right taxon first for 26% of challenge photos (chance about 5%) and finds a same-collection nearest specimen 75% of the time. The ring still shows parts of most specimens, so this mixes backdrop and specimen edges; it shows the surround carries collection identity strongly, not how much of the accuracy is backdrop alone.
- SigLIP2 is best on the polished hold-out (top-1 0.82 vs 0.67) but that hold-out shares one collection and backdrop with its references, so this is the same collection effect.
