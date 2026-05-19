# exp-20260508-015 Event Overlay Hold-Days Replay

Decision: `rejected`

Replay-only alpha search. Tests whether the current default-off event overlay plus non-generic state-surface add-on should use a different fixed hold horizon.

## Best Variant Vs Current 10d Overlay

| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL | Event trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5775 | 4.2598 | -0.3177 | $94,576.35 | $94,243.07 | $-333.28 | 7 | $+10,024.63 |
| mid_weak | 2.2741 | 1.8941 | -0.3800 | $70,187.00 | $65,090.87 | $-5,096.13 | 8 | $+9,699.62 |
| old_thin | 0.3959 | 0.4826 | +0.0867 | $28,900.28 | $33,280.19 | $+4,379.91 | 5 | $+7,037.53 |

## Variant Summary

| Variant | EV Sum Vs Current | PnL Delta Vs Current | Windows EV Improved | Windows EV Regressed | Passed |
|---|---:|---:|---:|---:|---|
| hold_5d | -1.0304 | $-16,778.81 | 0 | 3 | False |
| hold_20d | -0.6110 | $-1,049.50 | 1 | 2 | False |

## Coverage

```json
{
  "hold_10d_current": {
    "eligible_fraction": 0.5926,
    "eligible_surfaces": [
      "broad_breadth_trend_persistence",
      "mid_dispersion_selective_leadership",
      "rotation_breakout_leadership"
    ],
    "eligible_total_pnl_before_scalar": 10504.08,
    "eligible_trade_count": 16,
    "event_trade_count": 27
  },
  "hold_20d": {
    "eligible_fraction": 0.6,
    "eligible_surfaces": [
      "broad_breadth_trend_persistence",
      "mid_dispersion_selective_leadership",
      "rotation_breakout_leadership"
    ],
    "eligible_total_pnl_before_scalar": 11228.37,
    "eligible_trade_count": 12,
    "event_trade_count": 20
  },
  "hold_5d": {
    "eligible_fraction": 0.5312,
    "eligible_surfaces": [
      "broad_breadth_trend_persistence",
      "mid_dispersion_selective_leadership",
      "rotation_breakout_leadership"
    ],
    "eligible_total_pnl_before_scalar": 3665.44,
    "eligible_trade_count": 17,
    "event_trade_count": 32
  }
}
```

## Decision Rationale

Rejected: hold_20d was the best alternate hold horizon, but it did not beat the current 10d event overlay with enough stable three-window EV improvement and materiality.

No production universe, ranking, sizing, exits, LLM, news, or order path changed.
