# Evaluation
Suites: museum, collector, field, pebble/weathered, confusion-pair, unknown/OOD, low-quality.
Primary reports: Top-1, Top-3, macro F1, per-class recall, calibration, unknown false-accept rate, abstention coverage, confident-error rate.
Predictions are persisted before ground truth is revealed.

## Conventions (services/evaluator/metrics.py)
- OOD cases have truth `UNKNOWN`; the correct answer is to abstain. They are excluded from accuracy and drive the unknown false-accept rate.
- Abstentions count as misses in top-k accuracy; coverage and selective accuracy report the trade-off.
- A case may list extra accepted labels (e.g. a marble specimen where Calcite is also acceptable).
- Predictions are frozen in an append-only ledger with a sha256 before any label is revealed (`services/evaluator/harness.py`, `predictions` table in the Challenge Vault).
