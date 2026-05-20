# exp-20260520-018 Current-stack compound haircut skip

Decision: `rejected`

## Hypothesis

After the accepted current core stack, candidates with multiple independent severe <=0.25x sizing haircuts may still be negative replacement-value signals. Zero-sizing only that compound cohort could improve EV while preserving single-haircut winners.

## Gate 4

- passed: `False`
- best_variant: `compound_2plus_025x_skip`
- EV delta sum: `+0.1546`
- PnL delta sum: `$-11,082.03`
- EV windows improved/regressed: `1` / `1`
- skipped candidate count: `17`

## Three-window Deltas

| Window | EV delta | PnL delta | DD delta | Worst trade delta | Tail loss share delta | Trades delta | Skipped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0000 | +0.00 | +0.0000 | +0.000000 | +0.000000 | +0 | 2 |
| `mid_weak` | +0.3343 | -3801.33 | -0.0571 | +0.000000 | +0.082362 | -4 | 6 |
| `old_thin` | -0.1797 | -7280.70 | +0.0001 | -0.008271 | -0.106028 | -2 | 9 |

## Production Impact

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: true
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
```

No production order path changed.
