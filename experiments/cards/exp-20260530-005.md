# exp-20260530-005 FINRA Short-Pressure IWM-Confirmed Candidate Pool

Decision: `rejected_finra_short_pressure_iwm_confirmed`.

Single variable: require IWM 20-day return to lead SPY by at least 30bp before admitting the FINRA short-pressure breakout default-off paper candidate.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.5510 | +0.3882 | $117,072.92 | $122,003.37 | $+4,930.45 | +0.0003 | 15 | 17 |
| mid_weak | 2.1402 | 2.1986 | +0.0584 | $78,110.11 | $79,662.78 | $+1,552.67 | +0.0004 | 20 | 32 |
| old_thin | 0.5911 | 0.8024 | +0.2113 | $39,667.96 | $47,204.19 | $+7,536.23 | -0.0063 | 15 | 22 |

## Aggregate

- EV delta: `0.6579` (`0.083341`)
- PnL delta: `$14019.35` (`0.059695`)
- target trades: `50` across `3` windows
- max single positive share: `0.415003`
- positive PnL HHI: `0.239798`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0004,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.415003,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.239798,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 50,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exits, LLM, or news behavior changed.

No JavaScript was used.
