# exp-20260511-009 Space Static-Pool Risk Scalar

Decision: `rejected_static_pool_risk_scalar`.

## Sweep

| Scalar | Gate | Agg EV d | Agg PnL d | Max DD worsen | Space PnL | Space trades |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1.0 | fail | 2.3036 | 64577.73 | 0.0356 | 79995.67 | 25 |
| 0.75 | fail | 1.5218 | 42442.28 | 0.0198 | 59920.72 | 25 |
| 0.5 | fail | 0.6458 | 19578.75 | 0.0188 | 39503.38 | 25 |
| 0.25 | fail | -0.3026 | -3352.98 | 0.0219 | 19378.58 | 25 |

## Best Three-Window Comparison

Best scalar: `1.0`.

| Window | Base EV | After EV | dEV | Base DD | After DD | Space PnL | Space trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.2340 | 4.3549 | 0.1209 | 0.0548 | 0.0641 | 11303.70 | 9 |
| mid_weak | 1.6689 | 3.6041 | 1.9352 | 0.0941 | 0.0599 | 45841.80 | 9 |
| old_thin | 0.3853 | 0.6328 | 0.2475 | 0.0815 | 0.1171 | 22850.17 | 7 |

## Interpretation

Risk scalar alone does not turn the static Space pool into acceptable alpha. Continue only with event-dated forward replacement value or a non-hindsight official-catalyst discriminator.

## Production Impact

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  alters_orders: false
  alters_signal_generation: false
  alters_candidate_ranking: false
  alters_sizing: false
```
