# exp-20260605-013 Broad Low-Beta Residual Momentum

Decision: `rejected_broad_low_beta_residual_momentum_candidate_pool`.

Single variable: a replay-only/default-off broad OHLCV source admits top-1/day stocks with strong beta-adjusted residual momentum and low SPY beta/correlation.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 6.7477 | +1.5849 | $117,072.92 | $133,085.61 | $+16,012.69 | -0.0019 | 84 | 184 |
| mid_weak | 2.1402 | 1.9548 | -0.1854 | $78,110.11 | $74,608.87 | $-3,501.24 | +0.0007 | 61 | 89 |
| old_thin | 0.5911 | 0.1945 | -0.3966 | $39,667.96 | $18,696.95 | $-20,971.01 | +0.0872 | 103 | 227 |

## Aggregate

- EV delta: `1.0029` (`0.127044`)
- PnL delta: `$-8459.56` (`-0.036021`)
- target trades: `248` across `3` windows
- max single positive share: `0.342821`
- positive PnL HHI: `0.20604`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": false,
  "failed_reasons": [
    "aggregate_pnl_not_positive",
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0872,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.342821,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.20604,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 248,
  "target_trade_count_min": 20,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM/news, or live/default behavior changed.

No JavaScript was used.
