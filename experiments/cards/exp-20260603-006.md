# exp-20260603-006 FINRA Borrow-Pressure Candidate Pool

Decision: `accepted_candidate_finra_borrow_pressure`.

Single variable: require latest published FINRA days-to-cover >= 3.0 and short-interest change pct > 0.0 before admitting the accepted FINRA/IWM/cooldown default-off paper candidate.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates before | Borrow rejects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2882 | +0.1254 | $117,072.92 | $118,565.73 | $+1,492.81 | -0.0003 | 6 | 13 | 7 |
| mid_weak | 2.1402 | 2.1718 | +0.0316 | $78,110.11 | $78,688.14 | $+578.03 | -0.0004 | 8 | 18 | 10 |
| old_thin | 0.5911 | 0.6926 | +0.1015 | $39,667.96 | $43,285.24 | $+3,617.28 | -0.0027 | 8 | 13 | 3 |

## Aggregate

- EV delta: `0.2585` (`0.032746`)
- PnL delta: `$5688.12` (`0.02422`)
- target trades: `22` across `3` windows
- max single positive share: `0.383087`
- positive PnL HHI: `0.232995`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [],
  "max_drawdown_worse": -0.0003,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.383087,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.232995,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 22,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exits, LLM, or news behavior changed. Promotion requires a shared run/backtest adapter with parity tests.

No JavaScript was used.
