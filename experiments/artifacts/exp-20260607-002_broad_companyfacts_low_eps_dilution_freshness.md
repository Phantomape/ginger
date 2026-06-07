# exp-20260607-002 Broad Companyfacts Low EPS Dilution Freshness Candidate Pool

- Trial family: `broad_companyfacts_eps_dilution_freshness_candidate_pool`
- Changed variable: `broad_companyfacts_low_eps_dilution_freshness_candidate_source_v1`
- Decision: `rejected_broad_companyfacts_low_eps_dilution_freshness_candidate_pool`
- Aggregate EV delta: +0.4494
- Aggregate PnL delta: $+6,616.43
- Target trades: 319
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 116 | $7,091.94 | 5.1628 | 5.6101 | +0.4473 | $+8,152.72 | -0.0007 |
| mid_weak | 120 | $1,185.55 | 2.1402 | 2.2264 | +0.0862 | $+1,122.82 | -0.0040 |
| old_thin | 83 | $-1,968.98 | 0.5911 | 0.5070 | -0.0841 | $-2,659.11 | +0.0096 |

## Gate 4

- `passed`: `False`
- `status`: `rejected`
- `decision`: `rejected_broad_companyfacts_low_eps_dilution_freshness_candidate_pool`
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

This runner changes no production code. A positive result would require a separate shared default-off Companyfacts EPS-dilution freshness adapter, daily production exposure of the same filed-date-safe revenue/basic EPS/diluted EPS freshness fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, watchlist, sizing, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260607_002_broad_companyfacts_low_eps_dilution_freshness.py

No JavaScript was used.
