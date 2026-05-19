# exp-20260512-113 Core RS20 Acceleration Risk

Decision: `rejected_core_rs20_acceleration_risk`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` signals that already have the shared `rs20_entry_state_leader` flag and also have positive 10d-over-20d momentum acceleration. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted signals |
|---:|:---:|---:|---:|---|---|---:|
| 1.05 | FAIL | +0.0115 | $+240.96 | late_strong, mid_weak | old_thin | 9 |
| 1.10 | FAIL | +0.0321 | $+458.23 | late_strong, mid_weak | old_thin | 10 |
| 1.15 | FAIL | +0.0576 | $+961.41 | late_strong, mid_weak | old_thin | 13 |
| 1.20 | FAIL | +0.0627 | $+1,058.62 | late_strong, mid_weak | old_thin | 15 |

Selected multiplier: `1.2`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.2899 | +0.0559 | $94,086.91 | $94,908.65 | $+821.74 | 0.8039 | 3 |
| mid_weak | 1.6689 | 1.6818 | +0.0129 | $61,813.40 | $62,290.17 | $+476.77 | 0.7925 | 5 |
| old_thin | 0.3853 | 0.3792 | -0.0061 | $28,544.11 | $28,304.22 | $-239.89 | 0.9167 | 7 |

Production impact: replay-only scout. Positive promotion requires shared `risk_engine` and `portfolio_engine` code plus attribution-key parity before live/default behavior changes.
