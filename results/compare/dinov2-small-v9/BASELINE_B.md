# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 2592 · challenge cases 141 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.454 |
| ranked_top3 | 0.674 |
| category_accuracy | 0.809 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.291 |
| selective_accuracy | 0.756 |
| confident_error_rate | 0.244 |
| top1 | 0.220 |
| top3 | 0.255 |
| macro_f1 | 0.213 |
| ece | 0.185 |

Verdicts: {'identified': 41, 'uncertain': 89, 'unknown': 11}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.biotite | 0.00 |
| min.magnetite | 0.00 |
| min.muscovite | 0.26 |
| rock.basalt | 0.00 |
| rock.chert | 0.18 |
| rock.gneiss | 0.08 |
| rock.granite | 0.53 |
| rock.limestone | 0.00 |
| rock.marble | 0.45 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.15 |
