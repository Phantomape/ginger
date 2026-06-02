# exp-20260602-012 Post-Earnings Peer Reaction Transfer

Decision: `rejected_post_earnings_peer_reaction_transfer`.

Single variable: exact-industry peer-transfer candidate source after a confirmed positive EPS-surprise issuer reaction.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Events | Issuer reactions | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1966 | +0.0338 | $117,072.92 | $117,571.67 | $+498.75 | +0.0000 | 7 | 31 | 14 | 7 |
| mid_weak | 2.1402 | 2.4748 | +0.3346 | $78,110.11 | $83,893.67 | $+5,783.56 | -0.0059 | 7 | 26 | 5 | 17 |
| old_thin | 0.5911 | 0.5675 | -0.0236 | $39,667.96 | $38,868.19 | $-799.77 | +0.0005 | 3 | 30 | 7 | 3 |

## Aggregate

- EV delta: `0.3448` (`0.043678`)
- PnL delta: `$5482.54` (`0.023345`)
- target trades: `17` across `3` windows
- max single positive share: `0.627972`
- positive PnL HHI: `0.463212`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "target_sample_too_small",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0005,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.627972,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.463212,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 17,
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
