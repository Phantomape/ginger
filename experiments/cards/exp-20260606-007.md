# exp-20260606-007 SEC Item 2.03 Credit Absorption Candidate Pool

- Trial family: `sec_item203_non_dilutive_credit_absorption_candidate_pool`
- Changed variable: `sec_item_203_non_dilutive_credit_absorption_candidate_source_v1`
- Decision: `rejected_sec_item203_credit_absorption_candidate_pool`
- Aggregate EV delta: +0.0396
- Aggregate PnL delta: $+598.25
- Target trades: 2
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 0 | $0.00 | 5.1628 | 5.2034 | +0.0406 | $+917.54 | +0.0000 |
| mid_weak | 1 | $228.45 | 2.1402 | 2.1563 | +0.0161 | $+300.09 | -0.0003 |
| old_thin | 1 | $-619.38 | 0.5911 | 0.5740 | -0.0171 | $-619.38 | +0.0000 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: True
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: False
- `target_window_count_passed`: False
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: False

## Rule

Select PIT-safe SEC 8-K feature rows with both item codes 1.01 and 2.03, exclude 2.02 and 3.02, require first usable trading-day close-location >= 0.6, volume_ratio_20d <= 3.0, nonnegative signal-day return, and nonnegative 20d excess return versus SPY. Entry is delayed to the next open after that close is known.

## Decision Rationale

One or more Gate 4 checks failed, so this SEC Item 1.01+2.03 credit absorption source is not retained or promoted.

## Production / Backtest Parity

This runner changes no production code. It uses only historical PIT-safe SEC filing feature rows, first usable trading-day OHLCV available after the close, and a delayed next-open paper entry. A positive result would still require a separate shared default-off SEC filing-feature adapter and parity tests before any report queue, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260606_007_sec_item203_credit_absorption_candidate_pool.py

No JavaScript was used.
