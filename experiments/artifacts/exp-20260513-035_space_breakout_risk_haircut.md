# exp-20260513-035 Space breakout risk haircut

## Hypothesis
Space sleeve PnL in the accepted exp-032 stack is dominated by trend_long. A single additional risk scalar on official Space breakout_long signals may improve expected value by reducing lower-quality breakout exposure without changing the pool, event labels, ranking, targets, stops, or LLM boundary.

## Single changed variable
`space_breakout_risk_scalar` applied after the accepted exp-032 attention overlay stack.

## Gate 4 summary
- Decision: `rejected`
- Best scalar: `0.25`
- Aggregate delta vs exp-032: EV `0.638000`, PnL `11753.00`

## Three-window deltas vs exp-032
| window | EV delta | PnL delta | max DD delta | trades | survival |
|---|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 22 | 0.758600 |
| mid_weak | 0.944900 | 11291.09 | 0.001500 | 23 | 0.653300 |
| old_thin | -0.306900 | 461.91 | -0.004800 | 25 | 0.855300 |

## Production impact
No shared production policy was changed by this experiment artifact. If accepted, the scalar must be promoted into `quant/space_catalyst_sleeve.py` and covered by parity tests before live use.
