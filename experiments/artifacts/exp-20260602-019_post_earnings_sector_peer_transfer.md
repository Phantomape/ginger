# exp-20260602-019 Post-Earnings Same-Sector Peer Transfer

Decision: `rejected_post_earnings_same_sector_peer_transfer`.

Single variable: same-sector peer-transfer candidate source after a confirmed positive EPS-surprise issuer reaction.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Events | Issuer reactions | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1126 | -0.0502 | $117,072.92 | $117,528.58 | $+455.66 | +0.0005 | 21 | 42 | 16 | 31 |
| mid_weak | 2.1402 | 2.6795 | +0.5393 | $78,110.11 | $88,135.07 | $+10,024.96 | -0.0032 | 13 | 42 | 6 | 32 |
| old_thin | 0.5911 | 0.9027 | +0.3116 | $39,667.96 | $49,332.55 | $+9,664.59 | +0.0131 | 18 | 48 | 10 | 23 |

## Aggregate

- EV delta: `0.8007` (`0.10143`)
- PnL delta: `$20145.21` (`0.085779`)
- target trades: `52` across `3` windows
- max single positive share: `0.45669`
- positive PnL HHI: `0.266993`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0131,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.45669,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.266993,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 52,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
