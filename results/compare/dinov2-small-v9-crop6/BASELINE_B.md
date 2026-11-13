# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 2592 · challenge cases 135 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.415 |
| ranked_top3 | 0.741 |
| category_accuracy | 0.837 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.274 |
| selective_accuracy | 0.730 |
| confident_error_rate | 0.270 |
| top1 | 0.200 |
| top3 | 0.244 |
| macro_f1 | 0.203 |
| ece | 0.171 |

Verdicts: {'identified': 37, 'uncertain': 91, 'unknown': 7}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.biotite | 0.00 |
| min.magnetite | 0.12 |
| min.muscovite | 0.11 |
| rock.basalt | 0.00 |
| rock.chert | 0.18 |
| rock.gneiss | 0.08 |
| rock.granite | 0.58 |
| rock.limestone | 0.08 |
| rock.marble | 0.43 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.00 |
