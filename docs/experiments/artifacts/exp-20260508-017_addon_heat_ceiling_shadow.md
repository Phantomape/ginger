# exp-20260508-017 add-on heat ceiling shadow replay

Run at: `2026-05-08T11:22:38.912580+00:00`

## Hypothesis

Confirmed day-2 follow-through winners still have positive marginal expectancy, but current portfolio heat prevents part of that exposure. If the bottleneck is material across canonical windows, the next alpha direction should be an add-on reserve or state-specific add-on heat discriminator rather than more trigger tuning.

## Decision

`rejected_for_production_policy` - Shadow add-on heat removal improved EV in all three windows, but it weakens a hard portfolio risk cap and passes Gate 4 only by aggregate PnL. Use the result to pursue a narrower add-on reserve/discriminator, not to raise or remove production heat caps.

## Three-window result

| window | before EV | after EV | EV delta | before PnL | after PnL | PnL delta | sharpe delta | max DD delta | Gate4 | add-ons before -> after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| late_strong | 3.7435 | 4.0674 | 0.3239 | 83562.53 | 90788.88 | 7226.35 | 0.0 | 0.0 | PASS | 4/7 -> 7/7 |
| mid_weak | 1.5478 | 1.6195 | 0.0717 | 57542.74 | 59540.63 | 1997.89 | 0.03 | 0.0 | FAIL | 5/7 -> 7/7 |
| old_thin | 0.3359 | 0.3583 | 0.0224 | 26242.68 | 27347.42 | 1104.74 | 0.03 | -0.0002 | FAIL | 2/4 -> 4/4 |

## Ceiling attribution

| window | scheduled | requested shares | executed shares | unfilled shares | executed add-on PnL est. | unfilled upper-bound PnL | unmatched |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7 | 1010 | 254 | 756 | 2805.16 | 10445.02 | 0 |
| mid_weak | 7 | 854 | 690 | 164 | 6025.22 | 2965.03 | 0 |
| old_thin | 4 | 415 | 31 | 384 | 1089.39 | 3255.83 | 0 |

## Aggregate

- EV delta sum: `0.418`
- PnL delta sum: `10328.98`
- PnL delta pct: `0.061722`
- Windows with EV improvement: `3/3`
- Windows passing per-window Gate 4: `1/3`

## Production parity

Replay only. No production policy, backtester adapter, run adapter, candidate universe, ranking, sizing, stop, LLM, or news behavior changed.

The positive shadow is not production-safe as-is because it weakens add-on hard risk control. Any follow-up must be implemented as shared production/backtest policy and covered by parity tests before enabling.

