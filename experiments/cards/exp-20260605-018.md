# exp-20260605-018 SEC Operational 8-K Absorption Candidate Pool

- Trial family: `sec_operational_8k_absorption_candidate_pool`
- Changed variable: `sec_operational_8k_quiet_absorption_delayed_entry_candidate_source_v1`
- Decision: `rejected_sec_operational_8k_absorption_candidate_pool`
- Aggregate EV delta: -0.1367
- Aggregate PnL delta: $-162.52
- Target trades: 41
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 16 | $-2,310.24 | 5.1628 | 4.9164 | -0.2464 | $-1,392.70 | +0.0009 |
| mid_weak | 17 | $4,925.67 | 2.1402 | 2.3251 | +0.1849 | $+4,047.99 | +0.0000 |
| old_thin | 8 | $-2,817.82 | 0.5911 | 0.5159 | -0.0752 | $-2,817.81 | +0.0011 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: False
- `aggregate_pnl_positive`: False
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Rule

Select PIT-safe SEC 8-K feature rows with operational item codes 1.01/7.01/8.01, exclude earnings/financing/governance items, require first usable trading-day close-location >= 0.55, volume_ratio_20d <= 1.25, nonnegative signal-day return, and nonnegative 20d excess return versus SPY. Entry is delayed to the next open after that close is known.

## Decision Rationale

One or more Gate 4 checks failed, so this SEC operational 8-K absorption candidate source is not retained or promoted.

## Production / Backtest Parity

This runner changes no production code. It uses only historical PIT-safe SEC filing feature rows, first usable trading-day OHLCV available after the close, and a delayed next-open paper entry. A positive result would still require a separate shared default-off SEC filing-feature adapter and parity tests before any report queue, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_018_sec_operational_8k_absorption_candidate_pool.py

No JavaScript was used.
