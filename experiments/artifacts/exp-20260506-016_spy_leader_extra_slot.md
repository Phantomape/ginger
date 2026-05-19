# exp-20260506-016: SPY-leader extra slot

Decision: rejected

## Best Variant

- Best: `spy_leader_extra_slot_scarce_only`
- Gate 4 passed: `False`
- Aggregate EV delta: `-0.1677`
- Aggregate PnL delta: `-9158.81`

## Window Metrics

| Window | EV before | EV after | PnL delta | Sharpe delta | DD delta | Trades delta | Extra-slot promotions |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.4191 | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| mid_weak | 1.4415 | 1.4415 | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| old_thin | 0.3179 | 0.1502 | -9158.81 | -0.32 | 0.0006 | 1.0 | 3 |

## Interpretation

The conditional extra-slot leader sleeve did not clear Gate 4. Either the fifth-slot slice is not the binding opportunity-cost bottleneck, or the marginal leader candidate is not strong enough without a richer state discriminator.

Production impact: replay-only experiment. No live order, ranking, sizing, entry policy, or run.py behavior changed.
