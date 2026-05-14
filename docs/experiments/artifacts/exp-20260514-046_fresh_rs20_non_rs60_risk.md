# exp-20260514-046 Fresh RS20 Non-RS60 Risk

Decision: `rejected_fresh_rs20_non_rs60_risk`.

Single variable: cap-aware post-sizing share multiplier for already-qualified `trend_long` and `breakout_long` signals where `rs20_entry_state_leader=true` and `rs60_top_quintile_state=false`. Entries, exits, ranking, universe, LLM/news, heat, slots, and every other sizing rule stayed fixed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | +0.0399 | $+895.79 | late_strong, mid_weak | old_thin | 18 | +0.0012 |
| 1.050 | FAIL | +0.0753 | $+1,702.21 | late_strong, mid_weak | old_thin | 20 | +0.0032 |
| 1.075 | FAIL | +0.1186 | $+2,590.51 | late_strong, mid_weak | old_thin | 20 | +0.0049 |
| 1.100 | FAIL | +0.1358 | $+3,220.77 | late_strong, mid_weak | old_thin | 20 | +0.0069 |

Selected multiplier: `1.1`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Worst Trade d | Tail Loss d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.6148 | +0.1295 | $103,112.67 | $105,116.47 | $+2,003.80 | -0.0003 | +0.0000 | +0.0007 | 0.8039 | 11 |
| mid_weak | 1.8580 | 1.8733 | +0.0153 | $69,070.09 | $70,691.05 | $+1,620.96 | +0.0069 | +0.0000 | -0.0128 | 0.7925 | 5 |
| old_thin | 0.4749 | 0.4659 | -0.0090 | $33,921.46 | $33,517.47 | $-403.99 | +0.0019 | +0.0000 | +0.0051 | 0.9167 | 4 |

Production impact: replay-only scout unless Gate 4 passes and the same state is promoted into shared `portfolio_engine.py` code with attribution parity. The state fields are already produced by shared `risk_engine.py`.
