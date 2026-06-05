# exp-20260605-011 Broad Companyfacts Dual-Growth RS Candidate Pool

- Trial family: `broad_universe_companyfacts_candidate_pool`
- Changed variable: `broad_companyfacts_dual_growth_rs_candidate_source_v1`
- Decision: `rejected_broad_companyfacts_dual_growth_rs_candidate_pool`
- Aggregate EV delta: +0.1227
- Aggregate PnL delta: $+4,719.21
- Target trades: 336
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 110 | $5,734.23 | 5.1628 | 5.3461 | +0.1833 | $+6,394.07 | +0.0001 |
| mid_weak | 125 | $-177.80 | 2.1402 | 2.1754 | +0.0352 | $+1,573.86 | +0.0026 |
| old_thin | 101 | $-2,906.85 | 0.5911 | 0.4953 | -0.0958 | $-3,248.72 | +0.0168 |

## Gate 4

- `passed`: `False`
- `status`: `rejected`
- `decision`: `rejected_broad_companyfacts_dual_growth_rs_candidate_pool`
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

This runner changes no production code. A positive result would require a separate shared default-off Companyfacts broad-universe adapter, daily production exposure of the same PIT growth fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool.py

No JavaScript was used.
