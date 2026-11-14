# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-14 · reference photos 5471 · challenge cases 135 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.370 |
| ranked_top3 | 0.556 |
| category_accuracy | 0.778 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.200 |
| selective_accuracy | 0.741 |
| confident_error_rate | 0.259 |
| top1 | 0.148 |
| top3 | 0.170 |
| macro_f1 | 0.131 |
| ece | 0.253 |

Verdicts: {'identified': 27, 'uncertain': 96, 'unknown': 12}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.biotite | 0.00 |
| min.magnetite | 0.00 |
| min.muscovite | 0.06 |
| rock.basalt | 0.00 |
| rock.chert | 0.09 |
| rock.gneiss | 0.00 |
| rock.granite | 0.47 |
| rock.limestone | 0.00 |
| rock.marble | 0.43 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.00 |
