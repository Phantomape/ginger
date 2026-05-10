# exp-20260510-013 RS20 Fragility Guard

Decision: `rejected`

## Hypothesis

The accepted RS20 entry-state 1.10x top-up may be over-stacking with existing fragility haircuts; skipping the top-up only when any other sub-1 risk multiplier is already present could preserve RS20 upside while reducing weak-window drawdown.

## Aggregate

| EV before | EV after | EV delta | PnL delta | EV windows +/- | Guarded signals | Guarded closed trades | DD worst drift |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 6.2711 | 6.2707 | -0.0004 | -3.93 | 1/1 | 11 | 0 | 0.0 |

## Windows

| Window | EV before | EV after | EV delta | PnL delta | DD delta | Trades delta | Guarded signals | Guarded closed trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.234 | 4.234 | 0.0 | 0.0 | 0.0 | 0 | 1 | 0 |
| mid_weak | 1.6678 | 1.6673 | -0.0005 | -14.22 | 0.0 | 0 | 3 | 0 |
| old_thin | 0.3693 | 0.3694 | 0.0001 | 10.29 | 0.0 | 0 | 7 | 0 |

## Production Impact

Replay only. No shared policy, run adapter, entry, ranking, exit, add-on, LLM/news, or universe behavior changed.
