# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 1577 · challenge cases 190 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.263 |
| ranked_top3 | 0.526 |
| category_accuracy | 0.789 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.095 |
| selective_accuracy | 0.722 |
| confident_error_rate | 0.278 |
| top1 | 0.068 |
| top3 | 0.068 |
| macro_f1 | 0.081 |
| ece | 0.342 |

Verdicts: {'identified': 18, 'uncertain': 153, 'unknown': 19}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.azurite | 0.12 |
| min.biotite | 0.00 |
| min.calcite | 0.00 |
| min.fluorite | 0.00 |
| min.gypsum | 0.00 |
| min.hematite | 0.00 |
| min.k-feldspar | 0.22 |
| min.magnetite | 0.00 |
| min.malachite | 0.00 |
| min.muscovite | 0.38 |
| min.pyrite | 0.00 |
| min.quartz | 0.00 |
| rock.basalt | 0.14 |
| rock.gneiss | 0.10 |
| rock.granite | 0.00 |
| rock.limestone | 0.00 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.00 |
| rock.slate | 0.00 |
