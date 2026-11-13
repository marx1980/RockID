# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 3778 · challenge cases 135 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.407 |
| ranked_top3 | 0.622 |
| category_accuracy | 0.770 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.267 |
| selective_accuracy | 0.667 |
| confident_error_rate | 0.333 |
| top1 | 0.178 |
| top3 | 0.222 |
| macro_f1 | 0.160 |
| ece | 0.153 |

Verdicts: {'identified': 36, 'uncertain': 84, 'unknown': 15}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

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
| rock.marble | 0.48 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.15 |
