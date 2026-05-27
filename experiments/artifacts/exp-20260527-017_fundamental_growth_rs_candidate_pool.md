# exp-20260527-017 Fundamental Growth + RS Candidate Pool

Decision: `rejected_fundamental_growth_rs_candidate_pool`.

Single variable: a default-off paper sleeve admits at most one current-production-universe ticker per day when PIT SEC Companyfacts growth and daily OHLCV RS proxy both pass.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3357 | +0.1729 | $117,072.92 | $121,818.08 | $+4,745.16 | -0.0020 | 103 | 379 | 113 | 14 |
| mid_weak | 2.1402 | 5.5402 | +3.4000 | $78,110.11 | $127,360.68 | $+49,250.57 | -0.0211 | 118 | 501 | 126 | 15 |
| old_thin | 0.5911 | 2.2197 | +1.6286 | $39,667.96 | $78,161.06 | $+38,493.10 | +0.1264 | 124 | 472 | 130 | 18 |

## Aggregate

- EV delta: `5.2015` (`0.65891`)
- PnL delta: `$92488.83` (`0.393819`)
- target trades: `345` across `3` windows
- max single positive share: `0.567534`
- positive PnL HHI: `0.376935`

## Candidate Audit

```json
{
  "late_strong": {
    "candidate_days": 113,
    "candidate_source_tickers": 38,
    "combined_raw_candidates": 379,
    "context_checked": 4674,
    "fundamental_points_passed": 2581,
    "raw_candidates": 379,
    "rs_proxy_passed": 528,
    "rule_version": "fundamental_growth_rs_candidate_pool_v1",
    "trading_days": 123,
    "trend_liquidity_passed": 489,
    "unique_candidate_tickers": 14,
    "unique_fundamental_pass_tickers": 22
  },
  "mid_weak": {
    "candidate_days": 126,
    "candidate_source_tickers": 38,
    "combined_raw_candidates": 501,
    "context_checked": 4826,
    "fundamental_points_passed": 2481,
    "raw_candidates": 501,
    "rs_proxy_passed": 619,
    "rule_version": "fundamental_growth_rs_candidate_pool_v1",
    "trading_days": 127,
    "trend_liquidity_passed": 616,
    "unique_candidate_tickers": 15,
    "unique_fundamental_pass_tickers": 22
  },
  "old_thin": {
    "candidate_days": 130,
    "candidate_source_tickers": 38,
    "combined_raw_candidates": 472,
    "context_checked": 5244,
    "fundamental_points_passed": 2925,
    "raw_candidates": 472,
    "rs_proxy_passed": 623,
    "rule_version": "fundamental_growth_rs_candidate_pool_v1",
    "trading_days": 138,
    "trend_liquidity_passed": 581,
    "unique_candidate_tickers": 18,
    "unique_fundamental_pass_tickers": 24
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.1264,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.567534,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.376935,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 345,
  "target_trade_count_min": 30,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
