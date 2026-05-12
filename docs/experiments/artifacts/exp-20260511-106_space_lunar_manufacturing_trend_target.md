# exp-20260511-106 Space Lunar/Manufacturing Trend Target

Decision: `rejected_lunar_manufacturing_trend_target_extension`

Single variable: LUNR/RDW trend_long target ATR multiple inside the default-off official Space sleeve.

| Variant | Window | EV | EV delta vs accepted | PnL delta vs accepted | Trades | Max DD | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_exp105_stack | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| accepted_exp105_stack | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| accepted_exp105_stack | old_thin | 0.7694 | +0.0000 | +0.00 | 24 | 0.1012 | 0.8919 |
| lunar_manufacturing_6_0 | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| lunar_manufacturing_6_0 | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| lunar_manufacturing_6_0 | old_thin | 0.5829 | -0.1865 | -7,043.16 | 23 | 0.1012 | 0.9054 |
| lunar_manufacturing_7_0 | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| lunar_manufacturing_7_0 | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| lunar_manufacturing_7_0 | old_thin | 0.6906 | -0.0788 | -4,380.35 | 24 | 0.1012 | 0.8462 |

## Best Variant

- Best variant: `lunar_manufacturing_7_0`
- Aggregate EV delta vs accepted: `-0.0788`
- Aggregate PnL delta vs accepted: `$-4,380.35`
- Gate 4 passed: `False`

## Interpretation

LUNR/RDW trend target extension did not beat the accepted exp-105 Space stack under the three-window gate. Keep non-launch official Space trend signals at the accepted 5 ATR target.

## Production Impact

Default-off Space metadata experiment. Live Space slots remain zero; no core production orders, ranking, or signal generation changed.
