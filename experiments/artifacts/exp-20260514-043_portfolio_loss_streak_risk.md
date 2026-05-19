# exp-20260514-043 Portfolio Loss-Streak Risk

Decision: `rejected_portfolio_loss_streak_risk`.

Single variable: post-sizing risk multiplier after the last N closed core trades were all losses. No entry filter, ranking, exit, target, universe, LLM/news, event sleeve, slot, or existing sizing rule changed.

## Sweep

| Variant | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---|:---:|---:|---:|---|---|---:|---:|
| loss2_050x | FAIL | -0.3008 | $-25,681.08 | late_strong | mid_weak, old_thin | 28 | +0.0000 |
| loss2_075x | FAIL | -0.0692 | $-10,400.83 | late_strong | mid_weak, old_thin | 28 | +0.0000 |
| loss3_050x | FAIL | -0.4891 | $-20,868.46 | - | mid_weak, old_thin | 22 | +0.0000 |
| loss3_075x | FAIL | -0.1763 | $-8,011.71 | - | mid_weak, old_thin | 22 | +0.0000 |

Selected variant: `loss2_075x`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.5773 | +0.0920 | $103,112.67 | $100,161.52 | $-2,951.15 | -0.0064 | 0.8039 | 1 |
| mid_weak | 1.8580 | 1.7131 | -0.1449 | $69,070.09 | $63,916.50 | $-5,153.59 | +0.0000 | 0.7925 | 10 |
| old_thin | 0.4749 | 0.4586 | -0.0163 | $33,921.46 | $31,625.37 | $-2,296.09 | -0.0187 | 0.9167 | 17 |

Production impact: replay-only scout. Positive promotion requires shared production-visible closed-trade state, a shared sizing policy, and parity tests before any live/default behavior change.
