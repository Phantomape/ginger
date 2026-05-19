# Form 4 Satellite Overlay

- experiment_id: `exp-20260504-034`
- timestamp: `2026-05-04T13:14:51+00:00`
- decision: `positive_sample_not_material_no_promotion`
- production_impact: `experiment_only_no_live_or_default_backtest_strategy_change`

## Hypothesis

A bounded Form 4 meaningful-purchase event stream may improve portfolio-level expected value when added as a separate 10k-notional, one-position satellite overlay that does not consume core A/B slots.

## Three-Window Results

| Window | Baseline EV | Overlay EV | Delta EV | Baseline PnL | Overlay PnL | Event PnL | Trades | Win rate | Gate read |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| late_strong | 3.4191 | 3.5414 | 0.1223 | $78,600.33 | $81,038.18 | $1,799.63 | 19 -> 22 | 78.95% -> 81.82% | sample-only |
| mid_weak | 1.4415 | 1.5624 | 0.1209 | $55,015.08 | $57,229.74 | $1,991.30 | 21 -> 25 | 52.38% -> 52.00% | sample-only |
| old_thin | 0.3179 | 0.318 | 0.0001 | $24,642.07 | $24,648.18 | $6.11 | 22 -> 23 | 40.91% -> 43.48% | sample-only |

## Decision

The overlay added mostly profitable trades and did not regress EV in the majority read, but the EV/PnL lift was too small to justify adding live capital or complexity. Keep Form 4 in forward observation instead of promoting it.

## Next Action

Continue accumulating forward Form 4 paper-sleeve outcomes; retry promotion only after larger closed sample or a higher-capacity event discriminator appears.
