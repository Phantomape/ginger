# exp-20260523-016 - Backtest Atomic JSON Write

## Decision

Accepted as `measurement_repair`. This does not change entries, exits, filters, ranking, sizing, risk allocation, LLM behavior, or production orders.

## Defect

`data/backtests/backtest_results_20260522.json` parsed one full JSON object and then contained extra trailing data. That makes same-date result artifacts unsafe as Gate 1 baselines unless regenerated.

## Change

`quant/backtester.py` now writes JSON artifacts through `_atomic_write_json`, using a temp file in the target directory and `os.replace`.

Updated write paths:

- entry candidate event artifacts
- OHLCV snapshot artifacts
- daily `data/backtests/backtest_results_YYYYMMDD.json`

## Verification

- `py_compile` passed for `quant/backtester.py` and `quant/experiments/exp_20260523_015_core_alpha_upper_quartile_topup.py`
- atomic helper probe wrote parseable JSON and left no temp files
- `pytest quant/test_entry_day_ranking_attribution.py quant/test_backtester_pilot_sleeve.py` passed: 6 tests

## Production Status

No `run.py` change. No strategy promotion. This only improves backtest artifact integrity for future alpha experiments.
