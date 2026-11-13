# Baseline: onnx-community/dinov2-small (q8), specimen-balanced k-NN

Date 2026-11-13 · reference photos 2592 · challenge cases 189 (not embedded: 0)

Challenge photos come from photographers, specimens and source pages absent from the reference set.

## Shortlist (ignores the app's confidence verdict)

| metric | value |
|---|---|
| ranked_top1 | 0.487 |
| ranked_top3 | 0.762 |
| category_accuracy | 0.905 |

## Committed answers (verdict = identified)

| metric | value |
|---|---|
| coverage | 0.164 |
| selective_accuracy | 0.710 |
| confident_error_rate | 0.290 |
| top1 | 0.116 |
| top3 | 0.138 |
| macro_f1 | 0.151 |
| ece | 0.170 |

Verdicts: {'identified': 31, 'uncertain': 142, 'unknown': 16}. Thresholds calibrated on reference leave-one-specimen-out; challenge scored once.

| class | recall@1 (committed) |
|---|---|
| min.azurite | 0.25 |
| min.biotite | 0.00 |
| min.calcite | 0.00 |
| min.fluorite | 0.08 |
| min.gypsum | 0.31 |
| min.hematite | 0.00 |
| min.k-feldspar | 0.09 |
| min.magnetite | 0.00 |
| min.malachite | 0.00 |
| min.muscovite | 0.12 |
| min.pyrite | 0.20 |
| min.quartz | 0.00 |
| rock.basalt | 0.23 |
| rock.gneiss | 0.30 |
| rock.granite | 0.00 |
| rock.limestone | 0.10 |
| rock.quartzite | 0.00 |
| rock.sandstone | 0.09 |
| rock.slate | 0.00 |
