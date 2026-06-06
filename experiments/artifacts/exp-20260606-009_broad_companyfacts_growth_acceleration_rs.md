# exp-20260606-009 Broad Companyfacts Growth Acceleration RS Candidate Pool

- Trial family: `broad_companyfacts_growth_acceleration_candidate_pool`
- Changed variable: `broad_companyfacts_growth_acceleration_rs_candidate_source_v1`
- Decision: `rejected_broad_companyfacts_growth_acceleration_rs_candidate_pool`
- Aggregate EV delta: -0.1641
- Aggregate PnL delta: $+1,607.14
- Target trades: 298
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 105 | $-1,547.44 | 5.1628 | 4.8771 | -0.2857 | $-396.71 | -0.0007 |
| mid_weak | 105 | $4,834.93 | 2.1402 | 2.3272 | +0.1870 | $+4,122.87 | -0.0016 |
| old_thin | 88 | $-1,623.79 | 0.5911 | 0.5257 | -0.0654 | $-2,119.02 | +0.0148 |

## Gate 4

- `passed`: `False`
- `status`: `rejected`
- `decision`: `rejected_broad_companyfacts_growth_acceleration_rs_candidate_pool`
- `failed_reasons`: `['aggregate_ev_not_positive', 'window_ev_regression', 'window_pnl_regression']`
- `windows_ev_regressed`: `['late_strong', 'old_thin']`
- `windows_pnl_regressed`: `['late_strong', 'old_thin']`
- `drawdown_guard`: `<= 0.005`
- `target_trade_count_min`: `20`
- `target_window_count_min`: `3`
- `single_ticker_positive_share_guard`: `<= 0.5`
- `positive_pnl_hhi_guard`: `<= 0.3`
- `requires_parity_before_promotion`: `True`

## Production / Backtest Parity

This runner changes no production code. A positive result would require a separate shared default-off Companyfacts growth-acceleration adapter, daily production exposure of the same filed-date-safe acceleration fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, watchlist, sizing, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260606_009_broad_companyfacts_growth_acceleration_rs.py

No JavaScript was used.
