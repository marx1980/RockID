# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-14 · reference photos 5471 · challenge cases 189 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.402 |
| ranked_top3 | 0.688 |
| category_accuracy | 0.841 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.069 |
| selective_accuracy | 0.769 |
| confident_error_rate | 0.231 |
| top1 | 0.053 |
| top3 | 0.058 |
| macro_f1 | 0.060 |
| ece | 0.353 |

Verdicts: {'identified': 13, 'uncertain': 157, 'unknown': 19}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.azurite | 0.00 |
| min.biotite | 0.00 |
| min.calcite | 0.00 |
| min.fluorite | 0.00 |
| min.gypsum | 0.15 |
| min.hematite | 0.00 |
| min.k-feldspar | 0.17 |
| min.magnetite | 0.00 |
| min.malachite | 0.00 |
| min.muscovite | 0.00 |
| min.pyrite | 0.20 |
| min.quartz | 0.00 |
| rock.basalt | 0.15 |
| rock.gneiss | 0.00 |
| rock.granite | 0.00 |
| rock.limestone | 0.00 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.00 |
| rock.slate | 0.00 |
