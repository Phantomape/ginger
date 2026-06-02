# exp-20260602-023 Post-Earnings Pre-Event Underpriced Drift

Decision: `positive_replay_lead_not_promoted_requires_shared_adapter_and_forward_rows`.

Single variable: require `pre_event_rs20_vs_spy <= 0.0` on the exp-20260602-006 PIT positive-surprise drift source before daily top-1 paper selection.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates | RS rejects |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.4592 | +0.2964 | $117,072.92 | $119,721.96 | $+2,649.04 | -0.0015 | 5 | 6 | 14 |
| mid_weak | 2.1402 | 2.1920 | +0.0518 | $78,110.11 | $78,849.46 | $+739.35 | -0.0015 | 9 | 9 | 19 |
| old_thin | 0.5911 | 0.5976 | +0.0065 | $39,667.96 | $39,836.72 | $+168.76 | -0.0010 | 6 | 7 | 23 |

## Aggregate

- EV delta: `0.3547` (`0.044932`)
- PnL delta: `$3557.15` (`0.015146`)
- target trades: `20` across `3` windows
- max single positive share: `0.308744`
- positive PnL HHI: `0.192948`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [],
  "max_drawdown_worse": -0.001,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.308744,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.192948,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 20,
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
