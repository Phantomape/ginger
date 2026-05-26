# exp-20260526-011 QQQ-Confirmed Pullback-Reclaim Paper Sleeve

Decision: `rejected_pullback_reclaim_qqq_confirmed_sleeve`.

Single variable: a default-off paper sleeve admits at most one QQQ-confirmed liquid pullback-reclaim candidate per day, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3021 | +0.1393 | $117,072.92 | $120,226.74 | $+3,153.82 | +0.0037 | 32 | 87 | 33 | 25 |
| mid_weak | 2.1402 | 2.8133 | +0.6731 | $78,110.11 | $89,030.39 | $+10,920.28 | -0.0132 | 77 | 209 | 84 | 34 |
| old_thin | 0.5911 | 0.7565 | +0.1654 | $39,667.96 | $45,304.20 | $+5,636.24 | +0.0246 | 54 | 151 | 55 | 32 |

## Aggregate

- EV delta: `0.9778` (`0.123865`)
- PnL delta: `$19710.34` (`0.083927`)
- target trades: `163` across `3` windows
- max single positive share: `0.135492`
- positive PnL HHI: `0.086712`

## Pattern Audit

```json
{
  "late_strong": {
    "candidate_days": 33,
    "market_confirmation_rule_version": "qqq_gt_spy20_close_to_close_v1",
    "qqq_confirmed_liquid_pullback_reclaim_candidates": 87,
    "raw_pullback_reclaim_hits": 198,
    "raw_ticker_days_considered": 4674,
    "rule_version": "pullback_reclaim_qqq_confirmed_v1",
    "source_tickers_considered": 38,
    "unique_candidate_tickers": 25
  },
  "mid_weak": {
    "candidate_days": 84,
    "market_confirmation_rule_version": "qqq_gt_spy20_close_to_close_v1",
    "qqq_confirmed_liquid_pullback_reclaim_candidates": 209,
    "raw_pullback_reclaim_hits": 313,
    "raw_ticker_days_considered": 4826,
    "rule_version": "pullback_reclaim_qqq_confirmed_v1",
    "source_tickers_considered": 38,
    "unique_candidate_tickers": 34
  },
  "old_thin": {
    "candidate_days": 55,
    "market_confirmation_rule_version": "qqq_gt_spy20_close_to_close_v1",
    "qqq_confirmed_liquid_pullback_reclaim_candidates": 151,
    "raw_pullback_reclaim_hits": 270,
    "raw_ticker_days_considered": 5244,
    "rule_version": "pullback_reclaim_qqq_confirmed_v1",
    "source_tickers_considered": 38,
    "unique_candidate_tickers": 32
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0246,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.135492,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.086712,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 163,
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
