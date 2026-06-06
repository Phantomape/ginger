# exp-20260606-013 Broad Companyfacts Low EPS Dilution RS Candidate Pool

- Trial family: `broad_companyfacts_eps_dilution_candidate_pool`
- Changed variable: `broad_companyfacts_low_eps_dilution_rs_candidate_source_v1`
- Decision: `rejected_broad_companyfacts_low_eps_dilution_rs_candidate_pool`
- Aggregate EV delta: +0.4961
- Aggregate PnL delta: $+6,925.94
- Target trades: 320
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 116 | $7,307.80 | 5.1628 | 5.6449 | +0.4821 | $+8,368.57 | -0.0008 |
| mid_weak | 120 | $1,362.71 | 2.1402 | 2.2394 | +0.0992 | $+1,299.98 | -0.0040 |
| old_thin | 84 | $-2,052.48 | 0.5911 | 0.5059 | -0.0852 | $-2,742.61 | +0.0096 |

## Gate 4

- `passed`: `False`
- `status`: `rejected`
- `decision`: `rejected_broad_companyfacts_low_eps_dilution_rs_candidate_pool`
- `failed_reasons`: `['window_ev_regression', 'window_pnl_regression']`
- `windows_ev_regressed`: `['old_thin']`
- `windows_pnl_regressed`: `['old_thin']`
- `drawdown_guard`: `<= 0.005`
- `target_trade_count_min`: `20`
- `target_window_count_min`: `3`
- `single_ticker_positive_share_guard`: `<= 0.5`
- `positive_pnl_hhi_guard`: `<= 0.3`
- `requires_parity_before_promotion`: `True`

## Production / Backtest Parity

This runner changes no production code. A positive result would require a separate shared default-off Companyfacts EPS-dilution adapter, daily production exposure of the same filed-date-safe basic/diluted EPS fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, watchlist, sizing, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260606_013_broad_companyfacts_low_eps_dilution_rs.py

No JavaScript was used.
