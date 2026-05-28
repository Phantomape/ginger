# exp-20260528-034 Industry-Leadership No-Core-Overlap Paper Sleeve

Decision: `rejected_industry_leadership_no_core_overlap`.

Single variable: exclude industry-leadership paper candidates when any core A/B entry exists on the same signal date.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw | Kept | Removed overlap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.7405 | -0.4223 | $117,072.92 | $113,412.01 | $-3,660.91 | +0.0019 | 12 | 28 | 23 | 5 |
| mid_weak | 2.1402 | 2.8500 | +0.7098 | $78,110.11 | $90,188.07 | $+12,077.96 | -0.0062 | 33 | 67 | 58 | 9 |
| old_thin | 0.5911 | 0.6540 | +0.0629 | $39,667.96 | $41,917.08 | $+2,249.12 | -0.0018 | 16 | 30 | 27 | 3 |

## Aggregate

- EV delta: `0.3504` (`0.044388`)
- PnL delta: `$10666.17` (`0.045417`)
- target trades: `61` across `3` windows
- max single positive share: `0.592068`
- positive PnL HHI: `0.428888`

## Core-Overlap Audit

```json
{
  "late_strong": {
    "kept_candidate_count": 23,
    "kept_candidate_days": 17,
    "kept_top_industries": {
      "Semiconductors": 21,
      "Software - Application": 2
    },
    "kept_unique_tickers": 6,
    "raw_candidate_count": 28,
    "raw_candidate_days": 20,
    "removed_same_day_ab_overlap": 5,
    "removed_same_ticker_ab_overlap": 0,
    "removed_top_industries": {
      "Semiconductors": 4,
      "Software - Application": 1
    },
    "removed_unique_tickers": 5,
    "rule_version": "industry_leadership_no_core_overlap_v1"
  },
  "mid_weak": {
    "kept_candidate_count": 58,
    "kept_candidate_days": 34,
    "kept_top_industries": {
      "Semiconductors": 46,
      "Software - Application": 12
    },
    "kept_unique_tickers": 7,
    "raw_candidate_count": 67,
    "raw_candidate_days": 39,
    "removed_same_day_ab_overlap": 9,
    "removed_same_ticker_ab_overlap": 0,
    "removed_top_industries": {
      "Semiconductors": 7,
      "Software - Application": 2
    },
    "removed_unique_tickers": 6,
    "rule_version": "industry_leadership_no_core_overlap_v1"
  },
  "old_thin": {
    "kept_candidate_count": 27,
    "kept_candidate_days": 16,
    "kept_top_industries": {
      "Semiconductors": 12,
      "Software - Application": 15
    },
    "kept_unique_tickers": 8,
    "raw_candidate_count": 30,
    "raw_candidate_days": 19,
    "removed_same_day_ab_overlap": 3,
    "removed_same_ticker_ab_overlap": 1,
    "removed_top_industries": {
      "Semiconductors": 1,
      "Software - Application": 2
    },
    "removed_unique_tickers": 2,
    "rule_version": "industry_leadership_no_core_overlap_v1"
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0019,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.592068,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.428888,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 61,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
