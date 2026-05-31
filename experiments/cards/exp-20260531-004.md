# exp-20260531-004 Earnings-Imminent Pre-Event Exit

Decision: `rejected_earnings_imminent_pre_event_exit`.

Single variable: keep the exp-20260531-003 1-7 day surprise/RS candidate source fixed, but exit before the earnings event instead of holding ten trading days through the event.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.5515 | -0.6113 | $117,072.92 | $112,935.99 | $-4,136.93 | +0.0190 | 44 | 70 |
| mid_weak | 2.1402 | 2.4016 | +0.2614 | $78,110.11 | $83,095.83 | $+4,985.72 | -0.0043 | 50 | 87 |
| old_thin | 0.5911 | 0.7175 | +0.1264 | $39,667.96 | $44,293.19 | $+4,625.23 | +0.0140 | 54 | 123 |

## Aggregate

- EV delta: `-0.2235` (`-0.028312`)
- PnL delta: `$5474.02` (`0.023308`)
- target trades: `148` across `3` windows
- max single positive share: `0.240868`
- positive PnL HHI: `0.152075`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "aggregate_ev_not_positive",
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.019,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.240868,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.152075,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 148,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity test.

No JavaScript was used.
