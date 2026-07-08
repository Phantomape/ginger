# exp-20260708-006: Fundamental Growth RS Forward Readiness

- Status: `observed_only_rejected`
- Decision: `reject_activation_readiness_fundamental_growth_rs_forward_rows_20260707`
- Runner: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260708_006_fundamental_growth_rs_forward_readiness_20260707.py`
- Artifact: `data/experiments/exp-20260708-006/exp_20260708_006_fundamental_growth_rs_forward_readiness_20260707.json`

## Hypothesis

Observed-only alpha: accepted fundamental_growth_rs default-off paper sleeve now has materially more closed forward rows with cash/SPY/QQQ replacement value; test whether the fixed sleeve is activation-ready without retuning Companyfacts/OHLCV rules.

## Fixed Guard

- Enriched closed rows: `10` (watchlist min `20`, activation min `60`)
- Unique tickers: `5`; max single ticker share `0.3`

## Replacement Value

- Cash: sum `-4479.55`, mean `-447.96`, win rate `0.4`
- SPY: sum `-3091.31`, mean `-309.13`, win rate `0.4`
- QQQ: sum `-2225.5`, mean `-222.55`, win rate `0.4`

## Verdict

- Failed reasons: `min_watchlist_enriched_rows_not_met, min_activation_enriched_rows_not_met, replacement_value_vs_cash_usd_aggregate_not_positive, replacement_value_vs_cash_usd_win_rate_below_50pct, replacement_value_vs_spy_usd_aggregate_not_positive, replacement_value_vs_spy_usd_win_rate_below_50pct, replacement_value_vs_qqq_usd_aggregate_not_positive, replacement_value_vs_qqq_usd_win_rate_below_50pct, incomplete_replacement_value_rows`
- Why: The new settled rows are enough to reopen the sleeve surface for measurement, but not enough to promote it: only 10 enriched closed rows, one incomplete DDOG close, 4/10 winners, and negative aggregate replacement value versus cash, SPY, and QQQ.
- New evidence required: Do not reserve another fundamental_growth_rs forward-readiness ID until at least 20 enriched closed rows exist for a watchlist-lead refresh, and do not test activation envelope until at least 60 enriched closed rows exist with positive cash/SPY/QQQ replacement value and diversified ticker concentration.
