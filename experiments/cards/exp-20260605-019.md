# exp-20260605-019 SEC After-Hours 8-K Trend Candidate Pool

- Trial family: `sec_after_hours_operational_8k_candidate_pool`
- Changed variable: `sec_after_hours_operational_8k_prior_trend_candidate_source_v1`
- Decision: `rejected_sec_after_hours_8k_trend_candidate_pool`
- Aggregate EV delta: +0.1182
- Aggregate PnL delta: $+2,203.64
- Target trades: 42
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 13 | $1,942.57 | 5.1628 | 5.2430 | +0.0802 | $+1,815.59 | -0.0003 |
| mid_weak | 17 | $2,159.03 | 2.1402 | 2.2071 | +0.0669 | $+1,281.34 | -0.0001 |
| old_thin | 12 | $-893.30 | 0.5911 | 0.5622 | -0.0289 | $-893.29 | +0.0020 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: True
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Rule

Select PIT-safe SEC 8-K feature rows with operational item codes 1.01/7.01/8.01, exclude earnings/financing/governance items, require `accepted_datetime` at or after 20:00, require first usable trading-day close-location >= 0.55, and require nonnegative 20d excess return versus SPY. Entry is delayed to the next open after that close is known.

## Decision Rationale

One or more Gate 4 checks failed, so this SEC after-hours 8-K trend candidate source is not retained or promoted.

## Production / Backtest Parity

This runner changes no production code. It uses only historical PIT-safe SEC filing feature rows, observed accepted_datetime timing, first usable trading-day OHLCV available after the close, and a delayed next-open paper entry. A positive result would still require a separate shared default-off SEC filing-timing adapter and parity tests before any report queue, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_019_sec_after_hours_8k_trend_candidate_pool.py

No JavaScript was used.
