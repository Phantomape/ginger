# exp-20260714-005 USDA FAS export-sales agriculture basket

- Decision: `rejected_usda_fas_export_sales_agriculture_basket`
- Full-stack verdict: `reject`
- Settled releases / legs: `15` / `150`
- Window events: `{'old_thin': 7, 'mid_weak': 3, 'late_strong': 5}`
- Aggregate EV delta: `-0.0458`
- Aggregate PnL delta: `$-496.80`
- Gate 3 event survival: `19.75%`
- Positive-contribution tickers: `3`
- Top-five contribution: `1.0`
- Failed matched benchmarks: `['CASH', 'SPY', 'QQQ', 'DBA', 'CORN_SOYB_DIRECT']`
- Gate 4 failures: `['non_positive_aggregate_ev', 'non_positive_aggregate_pnl', 'insufficient_ev_improved_windows', 'ev_regressed_windows', 'single_ticker_positive_share_cap', 'top_5_contribution_pct_cap', 'hhi_concentration_cap', 'window_pnl_regression', 'positive_contribution_tickers_below_9', 'required_cash_spy_qqq_dba_corn_soyb_comparator_not_beaten', 'accepted_candidate_ev_not_beaten:exp-20260608-013', 'accepted_candidate_pnl_not_beaten:exp-20260608-013', 'accepted_candidate_ev_not_beaten:exp-20260611-007', 'accepted_candidate_pnl_not_beaten:exp-20260611-007']`
- DSR: `not_computable`

## Window deltas

- old_thin: events=7, legs=70, EV=-0.0278, PnL=$-492.47, drawdown=+0.0003.
- mid_weak: events=3, legs=30, EV=-0.0131, PnL=$-109.48, drawdown=+0.0002.
- late_strong: events=5, legs=50, EV=-0.0049, PnL=$+105.15, drawdown=-0.0011.

## Evidence contract

Every independent sample is one archived weekly USDA release; stock legs do not inflate the sample count. Current revisable ESR API values are excluded.

The daily snapshot is default-off and one-shot. No run.py, live order, core ranking, sizing, or exit path changed.

Reproduce offline: `.\.venv\Scripts\python.exe -B quant/experiments/exp_20260714_005_usda_fas_export_sales_agriculture_basket.py --offline`
