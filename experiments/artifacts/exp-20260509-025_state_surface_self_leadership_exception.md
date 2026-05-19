# exp-20260509-025 State-Surface Self-Leadership Exception

Decision: `rejected`

Alpha search, replay-only. Tests whether candidate-level 20-day self-leadership should make an exception to the state-surface benchmark-momentum gate.

## Three-Window Result

| Window | Exp14 Gate EV | Exception EV | vs Exp14 EV | vs Exp14 PnL | vs Exp14 Sharpe | vs Exp14 DD | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.8806 | 5.0920 | -0.7886 | $-7,882.34 | -0.36 | +0.71% | 12 |
| mid_weak | 3.0350 | 3.0350 | +0.0000 | $+0.00 | +0.00 | +0.00% | 18 |
| old_thin | 0.7936 | 0.9236 | +0.1300 | $+4,015.76 | +0.12 | +0.24% | 18 |

## Aggregate

- Versus exp-20260509-014 gate: EV -0.6586 (-6.78%), PnL $-3,866.58 (-1.59%), EV windows 1/1.

## Decision Rationale

Rejected: the self-leadership exception did not beat exp-20260509-014 with enough marginal EV/PnL materiality, window robustness, and late-risk preservation.

## Production Impact

Replay-only. No live/default orders, core A/B behavior, event sources, LLM/news behavior, sizing, exits, or adapters changed. A positive version would need shared default-off state_surface_sleeve.py parity before promotion.
