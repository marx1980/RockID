# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 1577 · challenge cases 190 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.516 |
| ranked_top3 | 0.805 |
| category_accuracy | 0.895 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.189 |
| selective_accuracy | 0.750 |
| confident_error_rate | 0.250 |
| top1 | 0.142 |
| top3 | 0.174 |
| macro_f1 | 0.180 |
| ece | 0.245 |

Verdicts: {'identified': 36, 'uncertain': 128, 'unknown': 26}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.azurite | 0.44 |
| min.biotite | 0.00 |
| min.calcite | 0.13 |
| min.fluorite | 0.08 |
| min.gypsum | 0.08 |
| min.hematite | 0.09 |
| min.k-feldspar | 0.17 |
| min.magnetite | 0.00 |
| min.malachite | 0.00 |
| min.muscovite | 0.25 |
| min.pyrite | 0.10 |
| min.quartz | 0.00 |
| rock.basalt | 0.21 |
| rock.gneiss | 0.20 |
| rock.granite | 0.20 |
| rock.limestone | 0.10 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.09 |
| rock.slate | 0.00 |
