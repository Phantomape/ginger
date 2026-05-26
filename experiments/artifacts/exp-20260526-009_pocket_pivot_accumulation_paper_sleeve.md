# exp-20260526-009 Pocket-Pivot Accumulation Paper Sleeve

Decision: `rejected_pocket_pivot_accumulation_paper_sleeve`.

Single variable: a default-off paper sleeve admits at most one QQQ-confirmed liquid pocket-pivot accumulation candidate per day, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 3.4014 | -1.7614 | $117,072.92 | $96,626.88 | $-20,446.04 | +0.0121 | 40 | 157 | 47 | 37 |
| mid_weak | 2.1402 | 2.8960 | +0.7558 | $78,110.11 | $90,502.90 | $+12,392.79 | -0.0045 | 85 | 326 | 90 | 38 |
| old_thin | 0.5911 | 0.3480 | -0.2431 | $39,667.96 | $29,493.72 | $-10,174.24 | +0.0526 | 57 | 185 | 59 | 37 |

## Aggregate

- EV delta: `-1.2487` (`-0.158181`)
- PnL delta: `$-18227.49` (`-0.077613`)
- target trades: `182` across `3` windows
- max single positive share: `0.268874`
- positive PnL HHI: `0.147207`

## Pattern Audit

```json
{
  "late_strong": {
    "candidate_days": 47,
    "qqq_confirmed_liquid_trend_candidates": 157,
    "raw_signal_day_pocket_pivot_hits": 476,
    "raw_ticker_days_considered": 4674,
    "rule_version": "pocket_pivot_accumulation_qqq_confirmed_v1",
    "source_tickers_considered": 38,
    "unique_candidate_tickers": 37
  },
  "mid_weak": {
    "candidate_days": 90,
    "qqq_confirmed_liquid_trend_candidates": 326,
    "raw_signal_day_pocket_pivot_hits": 557,
    "raw_ticker_days_considered": 4826,
    "rule_version": "pocket_pivot_accumulation_qqq_confirmed_v1",
    "source_tickers_considered": 38,
    "unique_candidate_tickers": 38
  },
  "old_thin": {
    "candidate_days": 59,
    "qqq_confirmed_liquid_trend_candidates": 185,
    "raw_signal_day_pocket_pivot_hits": 522,
    "raw_ticker_days_considered": 5244,
    "rule_version": "pocket_pivot_accumulation_qqq_confirmed_v1",
    "source_tickers_considered": 38,
    "unique_candidate_tickers": 37
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "max_drawdown_worse": 0.0526,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.268874,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.147207,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 182,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 2
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
