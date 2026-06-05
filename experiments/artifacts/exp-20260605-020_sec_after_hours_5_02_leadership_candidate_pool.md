# exp-20260605-020 SEC After-Hours Item 5.02 Leadership Candidate Pool

- Trial family: `sec_after_hours_5_02_leadership_candidate_pool`
- Changed variable: `sec_after_hours_8k_item_5_02_leadership_trend_candidate_source_v1`
- Decision: `rejected_sec_after_hours_5_02_leadership_candidate_pool`
- Aggregate EV delta: -0.0216
- Aggregate PnL delta: $+1,674.77
- Target trades: 25
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 11 | $-511.67 | 5.1628 | 5.0751 | -0.0877 | $+405.88 | +0.0008 |
| mid_weak | 7 | $1,467.62 | 2.1402 | 2.2143 | +0.0741 | $+1,539.26 | -0.0006 |
| old_thin | 7 | $-270.37 | 0.5911 | 0.5831 | -0.0080 | $-270.37 | +0.0033 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: False
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Rule

Select PIT-safe SEC 8-K feature rows with Item 5.02, exclude earnings, financing, and auditor-change co-items, require `accepted_datetime` at or after 20:00, require first usable trading-day close-location >= 0.55, and require nonnegative 20-day excess return versus SPY. Entry is delayed to the next open after that close is known.

## Decision Rationale

One or more Gate 4 checks failed, so this after-hours SEC Item 5.02 leadership-change candidate source is not retained or promoted.

## Production / Backtest Parity

This runner changes no production code. It uses only historical PIT-safe SEC filing feature rows, observed accepted_datetime timing, first usable trading-day OHLCV available after the close, and a delayed next-open paper entry. A positive result would still require a separate shared default-off SEC Item 5.02 leadership adapter and parity tests before any report queue, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_020_sec_after_hours_5_02_leadership_candidate_pool.py

No JavaScript was used.
