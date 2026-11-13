# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 636 · challenge cases 190 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.479 |
| ranked_top3 | 0.800 |
| category_accuracy | 0.926 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.153 |
| selective_accuracy | 0.759 |
| confident_error_rate | 0.241 |
| top1 | 0.116 |
| top3 | 0.137 |
| macro_f1 | 0.139 |
| ece | 0.173 |

Verdicts: {'identified': 29, 'uncertain': 140, 'unknown': 21}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.azurite | 0.12 |
| min.biotite | 0.00 |
| min.calcite | 0.00 |
| min.fluorite | 0.08 |
| min.gypsum | 0.08 |
| min.hematite | 0.09 |
| min.k-feldspar | 0.30 |
| min.magnetite | 0.00 |
| min.malachite | 0.00 |
| min.muscovite | 0.25 |
| min.pyrite | 0.00 |
| min.quartz | 0.00 |
| rock.basalt | 0.21 |
| rock.gneiss | 0.20 |
| rock.granite | 0.00 |
| rock.limestone | 0.10 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.18 |
| rock.slate | 0.00 |
