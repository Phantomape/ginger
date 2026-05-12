# exp-20260512-004 Space perfect-TQS risk

- Decision: `accepted_default_off_space_perfect_tqs_risk`
- Single variable: extra risk scalar for official Space signals whose TQS is capped at 1.0.
- Best variant: `perfect_tqs_1_5`
- Aggregate EV delta vs accepted: `+1.2496`
- Aggregate PnL delta vs accepted: `$+26,296.52`

## Sweep

| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |
|---|---:|---|---:|---:|---:|---:|---:|
| accepted_exp115_stack | 1.00 | fail | +0.0000 | +0.00 | 0 | 0 | 0 |
| perfect_tqs_1_1 | 1.10 | pass | +0.2144 | +4,802.29 | 2 | 0 | 9 |
| perfect_tqs_1_25 | 1.25 | pass | +0.6238 | +13,029.74 | 2 | 0 | 9 |
| perfect_tqs_1_5 | 1.50 | pass | +1.2496 | +26,296.52 | 2 | 0 | 9 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Perfect-TQS signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0287 | 5.0287 | +0.0000 | 106,092.97 | 106,092.97 | +0.00 | 23 | 0.0650 | 0.8070 | 2 |
| mid_weak | 4.3941 | 5.3999 | +1.0058 | 104,872.57 | 122,166.69 | +17,294.12 | 25 | 0.0471 | 0.7746 | 4 |
| old_thin | 0.8362 | 1.0800 | +0.2438 | 50,994.63 | 59,997.03 | +9,002.40 | 24 | 0.1056 | 0.8919 | 3 |

## Interpretation

The capped/perfect TQS bucket improved the accepted default-off Space stack under the three-window gate. Promotion should stay default-off metadata/helper only because Space live slots remain zero.
