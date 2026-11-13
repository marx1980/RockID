# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 9451 · challenge cases 135 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.311 |
| ranked_top3 | 0.481 |
| category_accuracy | 0.644 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.215 |
| selective_accuracy | 0.690 |
| confident_error_rate | 0.310 |
| top1 | 0.148 |
| top3 | 0.178 |
| macro_f1 | 0.129 |
| ece | 0.279 |

Verdicts: {'identified': 29, 'uncertain': 81, 'unknown': 25}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.biotite | 0.00 |
| min.magnetite | 0.00 |
| min.muscovite | 0.06 |
| rock.basalt | 0.00 |
| rock.chert | 0.09 |
| rock.gneiss | 0.00 |
| rock.granite | 0.53 |
| rock.limestone | 0.00 |
| rock.marble | 0.38 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.00 |
