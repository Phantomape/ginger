# exp-20260603-024 Alpha-Score VIX Regime Support

Decision: `rejected_alpha_score_vix_regime_support`.

Single variable: keep exp-20260531-021 alpha-score market-regime source fixed, but admit paper candidates only when free daily `VIX <= 25` on the signal date.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates after VIX |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.7091 | +0.5463 | $117,072.92 | $124,108.18 | $+7,035.26 | +0.0000 | 52 | 154 |
| mid_weak | 2.1402 | 2.8448 | +0.7046 | $78,110.11 | $90,603.09 | $+12,492.98 | -0.0024 | 62 | 285 |
| old_thin | 0.5911 | 0.9841 | +0.3930 | $39,667.96 | $52,910.24 | $+13,242.28 | -0.0062 | 37 | 174 |

## Aggregate

- EV delta vs core baseline: `1.6439` (`0.208244`)
- PnL delta vs core baseline: `$32770.52` (`0.139537`)
- target trades: `151` across `3` windows
- max single positive share: `0.274512`
- positive PnL HHI: `0.18724`

## Accepted Comparator

```json
{
  "accepted_after_expected_value_score": 9.538,
  "accepted_after_total_pnl": 267621.51,
  "comparator_artifact": "data/experiments/exp-20260531-021/exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional.json",
  "comparator_experiment_id": "exp-20260531-021",
  "current_after_expected_value_score": 9.538,
  "current_after_total_pnl": 267621.51,
  "delta_vs_accepted_expected_value_score": 0.0,
  "delta_vs_accepted_total_pnl": 0.0,
  "passed": false
}
```

## VIX Source

```json
{
  "cache_file": "data/experiments/exp-20260603-024/vix_daily_close_source.txt",
  "fallback_url": "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?period1=1727827200&period2=1776902400&interval=1d",
  "fetch_errors": [
    "FRED:VIXCLS: The read operation timed out"
  ],
  "known_at": "signal_day_close_before_next_open_paper_entry",
  "max_date": "2026-04-22",
  "min_date": "2024-10-02",
  "primary_url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
  "source_name": "Yahoo:^VIX",
  "status": "downloaded",
  "url": "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?period1=1727827200&period2=1776902400&interval=1d",
  "usable_rows": 389
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "accepted_comparator_underperformed"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.274512,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.18724,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 151,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result would still need shared FRED VIX ingestion and parity tests before activation.

No JavaScript was used.
