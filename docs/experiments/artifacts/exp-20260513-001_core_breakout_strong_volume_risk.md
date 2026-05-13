# exp-20260513-001 Core Breakout Strong-Volume Risk

Decision: `rejected_core_breakout_strong_volume_risk`.

Single variable: cap-aware post-sizing risk scalar for existing `breakout_long` signals with `conditions_met.volume_spike_ratio > 2.0`. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.75 | FAIL | -0.0101 | $-601.51 | - | mid_weak | 11 | +0.0000 |
| 1.05 | FAIL | +0.0002 | $+2.62 | mid_weak | - | 10 | +0.0000 |
| 1.10 | FAIL | +0.0000 | $-1.62 | - | - | 10 | +0.0000 |
| 1.25 | FAIL | -0.0097 | $-132.75 | - | mid_weak | 11 | +0.0000 |
| 1.50 | FAIL | -0.0129 | $-251.81 | - | mid_weak | 11 | +0.0000 |

Selected multiplier: `1.05`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.2340 | +0.0000 | $94,086.91 | $94,086.91 | $+0.00 | 0.8039 | 0 |
| mid_weak | 1.6689 | 1.6691 | +0.0002 | $61,813.40 | $61,816.02 | $+2.62 | 0.7925 | 8 |
| old_thin | 0.3853 | 0.3853 | +0.0000 | $28,544.11 | $28,544.11 | $+0.00 | 0.9167 | 2 |

Production impact: replay-only scout unless Gate 4 passes and the rule is promoted into shared sizing policy with parity coverage.
