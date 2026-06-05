# exp-20260605-034 SEC After-Hours Item 5.07 Governance Candidate Pool

- Trial family: `sec_after_hours_5_07_governance_candidate_pool`
- Changed variable: `sec_after_hours_8k_item_5_07_shareholder_vote_trend_candidate_source_v1`
- Decision: `rejected_sec_after_hours_5_07_governance_candidate_pool`
- Aggregate EV delta: -0.0158
- Aggregate PnL delta: $+1,733.93
- Target trades: 14
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4 | $-1,008.10 | 5.1628 | 5.0653 | -0.0975 | $-90.55 | +0.0009 |
| mid_weak | 8 | $1,423.45 | 2.1402 | 2.2130 | +0.0728 | $+1,495.09 | -0.0019 |
| old_thin | 2 | $329.39 | 0.5911 | 0.6000 | +0.0089 | $+329.39 | -0.0003 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: False
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: False
- `target_window_count_passed`: True
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Rule

Select PIT-safe SEC 8-K feature rows with Item 5.07, exclude earnings, financing, auditor-change, and Item 5.02 leadership co-items, require `accepted_datetime` at or after 20:00, require first usable trading-day close-location >= 0.55, and require nonnegative 20-day excess return versus SPY. Entry is delayed to the next open after that close is known.

## Decision Rationale

One or more Gate 4 checks failed, so this after-hours SEC Item 5.07 shareholder-vote candidate source is not retained or promoted.

## Production / Backtest Parity

This runner changes no production code. It uses historical PIT-safe SEC filing feature rows, observed accepted_datetime timing, first usable trading-day OHLCV available after the close, and a delayed next-open paper entry. A positive result would still require a separate shared default-off SEC Item 5.07 governance adapter and focused parity tests before any report queue, candidate priority, watchlist, sizing, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_034_sec_after_hours_5_07_governance_candidate_pool.py

No JavaScript was used.
