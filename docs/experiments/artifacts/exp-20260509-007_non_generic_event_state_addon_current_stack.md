# exp-20260509-007 Non-Generic Event State Add-On Current Stack

Decision: `promising_replay_only_non_generic_event_state_addon`

Alpha search. Current-stack revalidation of the event-bundle paper allocation add-on: 2.0x paper notional only for positive PIT state-score events on non-generic state surfaces.

## Best Variant Vs Full Bundle

| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5771 | 4.8980 | +0.3209 | $97,384.30 | $101,828.78 | $+4,444.48 | 9 | $+10,357.92 |
| mid_weak | 2.0830 | 2.3533 | +0.2703 | $67,850.50 | $72,186.99 | $+4,336.49 | 11 | $+13,344.80 |
| old_thin | 0.3938 | 0.4231 | +0.0293 | $28,745.97 | $30,005.02 | $+1,259.05 | 7 | $+2,657.59 |

## Aggregate Gate

- EV delta vs full bundle: +0.6205 (+8.80%)
- PnL delta vs full bundle: $+10,040.02 (+5.18%)
- EV windows improved/regressed: 3/0

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

Accepted as the current event-bundle allocation alpha lead for default-off paper optimization: non_generic_positive_add_200 beat the full frozen event bundle and the current core baseline across all three canonical windows with zero EV regressions. Production already exposes matching paper attribution fields, but live orders remain blocked until a shared trade-enabled event adapter, parity tests, and closed forward replacement-value outcomes exist.

## Production Impact

No live orders, default backtest strategy, core A/B behavior, LLM, or news path changed. Production already exposes the same default-off paper attribution schema; live capital still needs an explicit shared trade adapter and parity tests.
