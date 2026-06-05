# exp-20260605-026 Broad Companyfacts Profitability-Inflection RS

- Trial family: `broad_companyfacts_profitability_inflection_candidate_pool`
- Changed variable: `broad_companyfacts_profitability_inflection_rs_candidate_source_v1`
- Decision: `rejected_broad_companyfacts_profitability_inflection_rs_candidate_pool`
- Aggregate EV delta: -0.7768
- Aggregate PnL delta: $-4,671.08
- Target trades: 201
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 92 | $-6,448.88 | 5.1628 | 4.2942 | -0.8686 | $-6,110.68 | +0.0164 |
| mid_weak | 68 | $4,638.64 | 2.1402 | 2.3219 | +0.1817 | $+4,520.35 | -0.0018 |
| old_thin | 41 | $-3,080.76 | 0.5911 | 0.5012 | -0.0899 | $-3,080.75 | +0.0064 |

## Gate 4

- `passed`: `False`
- `status`: `rejected`
- `decision`: `rejected_broad_companyfacts_profitability_inflection_rs_candidate_pool`
- `failed_reasons`: `['aggregate_ev_not_positive', 'aggregate_pnl_not_positive', 'window_ev_regression', 'window_pnl_regression', 'window_drawdown_drift_too_high']`
- `windows_ev_regressed`: `['late_strong', 'old_thin']`
- `windows_pnl_regressed`: `['late_strong', 'old_thin']`
- `drawdown_guard`: `<= 0.005`
- `target_trade_count_min`: `20`
- `target_window_count_min`: `3`
- `single_ticker_positive_share_guard`: `<= 0.5`
- `positive_pnl_hhi_guard`: `<= 0.3`
- `requires_parity_before_promotion`: `True`
- `windows_drawdown_regressed`: `['late_strong', 'old_thin']`

## Production / Backtest Parity

This runner changes no production code. A positive result would require a separate shared default-off Companyfacts profitability-inflection adapter, production exposure of the same PIT filed-date-safe fields, and focused parity tests before any report queue, paper ledger, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_026_broad_companyfacts_profitability_inflection_rs.py

No JavaScript was used.
