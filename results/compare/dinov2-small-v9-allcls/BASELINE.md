# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 9451 · challenge cases 189 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.312 |
| ranked_top3 | 0.540 |
| category_accuracy | 0.820 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.048 |
| selective_accuracy | 0.556 |
| confident_error_rate | 0.444 |
| top1 | 0.026 |
| top3 | 0.037 |
| macro_f1 | 0.039 |
| ece | 0.101 |

Verdicts: {'identified': 9, 'uncertain': 150, 'unknown': 30}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.azurite | 0.00 |
| min.biotite | 0.00 |
| min.calcite | 0.00 |
| min.fluorite | 0.00 |
| min.gypsum | 0.15 |
| min.hematite | 0.00 |
| min.k-feldspar | 0.00 |
| min.magnetite | 0.00 |
| min.malachite | 0.00 |
| min.muscovite | 0.00 |
| min.pyrite | 0.20 |
| min.quartz | 0.00 |
| rock.basalt | 0.08 |
| rock.gneiss | 0.00 |
| rock.granite | 0.00 |
| rock.limestone | 0.00 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.00 |
| rock.slate | 0.00 |
