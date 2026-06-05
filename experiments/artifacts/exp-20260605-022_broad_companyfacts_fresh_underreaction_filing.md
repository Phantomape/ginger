# exp-20260605-022 Broad Companyfacts Fresh Underreaction Filing

- Trial family: `broad_companyfacts_fresh_underreaction_filing_candidate_pool`
- Changed variable: `broad_companyfacts_fresh_underreaction_filing_candidate_source_v1`
- Decision: `rejected_broad_companyfacts_fresh_underreaction_filing_candidate_pool`
- Aggregate EV delta: +0.0712
- Aggregate PnL delta: $+2,161.22
- Target trades: `29`
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 17 | $-188.99 | 5.1628 | 5.1479 | -0.0149 | $+728.56 | +0.0000 |
| mid_weak | 11 | $1,595.67 | 2.1402 | 2.2338 | +0.0936 | $+1,667.30 | -0.0013 |
| old_thin | 1 | $-234.64 | 0.5911 | 0.5836 | -0.0075 | $-234.64 | +0.0010 |

## Rule

Select filed-date-safe SEC Companyfacts events where revenue and positive profit growth are both at least 15%, the ticker did not outperform SPY over the prior 20 trading days before the filing, and the first usable trading day closes green near the high. Entry is delayed to the next open after that confirmation.

## Gate 4 Checks

- `decision`: `rejected_broad_companyfacts_fresh_underreaction_filing_candidate_pool`
- `drawdown_guard`: `<= 0.005`
- `failed_reasons`: `['window_ev_regression', 'window_pnl_regression']`
- `passed`: `False`
- `positive_pnl_hhi_guard`: `<= 0.3`
- `requires_parity_before_promotion`: `True`
- `single_ticker_positive_share_guard`: `<= 0.5`
- `status`: `rejected`
- `target_trade_count_min`: `20`
- `target_window_count_min`: `3`
- `windows_ev_regressed`: `['late_strong', 'old_thin']`
- `windows_pnl_regressed`: `['old_thin']`

## Production / Backtest Parity

This runner changes no production code. It uses only SEC Companyfacts growth rows with filed-date visibility, warehouse OHLCV known after the first usable trading-day close, and delayed next-open paper entry. A positive result would require a separate shared default-off fresh Companyfacts filing adapter, daily production exposure of the same filed-date and OHLCV confirmation fields, warehouse/snapshot replay parity, and focused tests before any report queue, paper ledger, candidate priority, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_022_broad_companyfacts_fresh_underreaction_filing.py

No JavaScript was used.
