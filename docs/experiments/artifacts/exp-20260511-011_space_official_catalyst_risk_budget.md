# exp-20260511-011 Space Official-Catalyst Risk Budget

Decision: `accepted_default_off_forward_hypothesis`.
Best scalar: `0.75`.

| Scalar | Gate | Agg EV d | Agg PnL d | Max DD worsen |
| ---: | --- | ---: | ---: | ---: |
| 1.0 | fail | 1.9591 | 46242.36 | 0.0348 |
| 0.75 | pass | 1.5598 | 32256.34 | 0.0197 |
| 0.5 | pass | 1.0541 | 17460.98 | 0.0198 |
| 0.25 | fail | 0.5024 | 2455.99 | 0.0229 |

## Best Three-Window Comparison

| Window | Base EV | After EV | dEV | Base DD | After DD | dDD | Space PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.2340 | 4.4465 | 0.2125 | 0.0548 | 0.0545 | -0.0003 | 4143.77 |
| mid_weak | 1.6689 | 2.7096 | 1.0407 | 0.0941 | 0.0470 | -0.0471 | 12229.77 |
| old_thin | 0.3853 | 0.6919 | 0.3066 | 0.0815 | 0.1012 | 0.0197 | 23109.53 |

## Interpretation

The official-catalyst Space subpool works best at a 0.75x risk budget: all three windows improved EV, aggregate EV/PnL rose, and drawdown damage stayed inside the 2 pp guard. This is a production-visible forward hypothesis only; live slots remain zero until closed forward replacement-value evidence passes.

## Production Impact

The daily Space shadow snapshot now exposes this forward hypothesis, but live slots remain zero and no order/ranking/sizing path changes.
