# exp-20260602-006 Post-Earnings Positive-Surprise Drift Candidate Pool

Decision: `rejected_post_earnings_positive_surprise_drift_candidate_pool`.

Single variable: a default-off paper source using PIT earnings snapshot transition-confirmed positive EPS surprise plus post-event OHLCV strength, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Events | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.8899 | -0.2729 | $117,072.92 | $114,248.52 | $-2,824.40 | +0.0014 | 18 | 48 | 20 |
| mid_weak | 2.1402 | 2.5037 | +0.3635 | $78,110.11 | $84,303.84 | $+6,193.73 | -0.0039 | 21 | 49 | 28 |
| old_thin | 0.5911 | 0.6288 | +0.0377 | $39,667.96 | $41,641.51 | $+1,973.55 | +0.0348 | 21 | 55 | 30 |

## Aggregate

- EV delta: `0.1283` (`0.016253`)
- PnL delta: `$5342.88` (`0.02275`)
- target trades: `60` across `3` windows
- max single positive share: `0.211831`
- positive PnL HHI: `0.111012`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0348,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.211831,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.111012,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 60,
  "target_trade_count_min": 20,
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
