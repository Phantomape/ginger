# exp-20260507-026 Non-Generic Event State Add-On

Decision: `promising_replay_only_non_generic_event_state_addon`

Replay-only alpha search. Tests a bounded event-satellite add-on for positive PIT state-score events on non-generic state surfaces.

## Best Variant Vs Full Bundle

| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1196 | 4.4473 | +0.3277 | $88,594.32 | $93,038.80 | $+4,444.48 | 9 | $+10,357.92 |
| mid_weak | 2.0019 | 2.2741 | +0.2722 | $65,850.51 | $70,187.00 | $+4,336.49 | 11 | $+13,344.80 |
| old_thin | 0.3676 | 0.3959 | +0.0283 | $27,641.23 | $28,900.28 | $+1,259.05 | 7 | $+2,657.59 |

## Variant Summary

| Variant | EV Sum Vs Full | PnL Delta Vs Full | Windows EV Improved | Windows EV Regressed | Passed |
|---|---:|---:|---:|---:|---|
| non_generic_positive_add_125 | +0.1610 | $+2,510.00 | 3 | 0 | False |
| non_generic_positive_add_150 | +0.3149 | $+5,020.02 | 3 | 0 | True |
| non_generic_positive_add_200 | +0.6282 | $+10,040.02 | 3 | 0 | True |

## Coverage

```json
{
  "eligible_fraction": 0.5926,
  "eligible_surfaces": [
    "broad_breadth_trend_persistence",
    "mid_dispersion_selective_leadership",
    "rotation_breakout_leadership"
  ],
  "eligible_total_pnl": 10504.08,
  "eligible_trade_count": 16,
  "event_trade_count": 27,
  "rule": "positive PIT state score and state_surface != balanced_state_leadership"
}
```

## Decision Rationale

Promising replay-only: non_generic_positive_add_200 beat the full frozen event bundle and core baseline across the three canonical windows without EV regression. Production use still requires a shared default-off adapter that computes the same PIT state-surface feature before any capital impact.

No production universe, ranking, sizing, exits, LLM, news, or order path changed.
