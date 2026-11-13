# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 1834 · challenge cases 190 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.495 |
| ranked_top3 | 0.800 |
| category_accuracy | 0.895 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.184 |
| selective_accuracy | 0.657 |
| confident_error_rate | 0.343 |
| top1 | 0.121 |
| top3 | 0.163 |
| macro_f1 | 0.169 |
| ece | 0.147 |

Verdicts: {'identified': 35, 'uncertain': 130, 'unknown': 25}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.azurite | 0.31 |
| min.biotite | 0.00 |
| min.calcite | 0.07 |
| min.fluorite | 0.08 |
| min.gypsum | 0.08 |
| min.hematite | 0.09 |
| min.k-feldspar | 0.09 |
| min.magnetite | 0.00 |
| min.malachite | 0.00 |
| min.muscovite | 0.25 |
| min.pyrite | 0.20 |
| min.quartz | 0.00 |
| rock.basalt | 0.21 |
| rock.gneiss | 0.20 |
| rock.granite | 0.20 |
| rock.limestone | 0.10 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.09 |
| rock.slate | 0.00 |
