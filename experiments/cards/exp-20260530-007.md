# exp-20260530-007 FINRA IWM Same-Ticker Cooldown Candidate Pool

Decision: `accepted_candidate_finra_iwm_same_ticker_cooldown`.

Single variable: add a seven-calendar-day same-ticker cooldown after an admitted FINRA short-pressure IWM-confirmed default-off paper candidate.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates | Cooldown rejects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2891 | +0.1263 | $117,072.92 | $118,592.97 | $+1,520.05 | +0.0003 | 13 | 13 | 4 |
| mid_weak | 2.1402 | 2.1782 | +0.0380 | $78,110.11 | $78,921.41 | $+811.30 | +0.0003 | 15 | 18 | 14 |
| old_thin | 0.5911 | 0.7576 | +0.1665 | $39,667.96 | $45,635.01 | $+5,967.05 | -0.0046 | 10 | 13 | 9 |

## Aggregate

- EV delta: `0.3308` (`0.041905`)
- PnL delta: `$8298.4` (`0.035335`)
- target trades: `38` across `3` windows
- max single positive share: `0.34534`
- positive PnL HHI: `0.194534`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [],
  "max_drawdown_worse": 0.0003,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.34534,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.194534,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 38,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exits, LLM, or news behavior changed. Promotion requires moving the same source and cooldown into a shared run/backtest adapter with parity tests.

No JavaScript was used.
