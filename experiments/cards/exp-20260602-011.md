# exp-20260602-011 Post-Earnings Surprise Underreaction

Decision: `rejected_post_earnings_surprise_underreaction_candidate_pool`.

Single variable: require `close_location <= 0.70` on the exp-20260602-006 PIT positive-surprise drift source before daily top-1 paper selection.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates | Cap rejects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2503 | +0.0875 | $117,072.92 | $118,251.80 | $+1,178.88 | +0.0000 | 5 | 5 | 15 |
| mid_weak | 2.1402 | 2.3146 | +0.1744 | $78,110.11 | $80,932.40 | $+2,822.29 | -0.0024 | 7 | 8 | 20 |
| old_thin | 0.5911 | 0.7250 | +0.1339 | $39,667.96 | $44,480.25 | $+4,812.29 | -0.0035 | 6 | 8 | 22 |

## Aggregate

- EV delta: `0.3958` (`0.050139`)
- PnL delta: `$8813.46` (`0.037528`)
- target trades: `18` across `3` windows
- max single positive share: `0.298295`
- positive PnL HHI: `0.201942`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "target_sample_too_small"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.298295,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.201942,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 18,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
