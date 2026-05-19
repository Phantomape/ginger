# exp-20260514-014 Dual-RS Persistent Leader Risk

Decision: `rejected_dual_rs_persistent_leader_risk_topup`.

Single variable: cap-aware post-sizing share multiplier for already-qualified `trend_long` and `breakout_long` signals that satisfy both `rs20_entry_state_leader` and `rs60_top_quintile_state`. No entry filter, ranking, exit, target, universe, LLM, news, Space, or portfolio heat behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | +0.0001 | $+571.28 | old_thin | late_strong | 11 | +0.0010 |
| 1.050 | FAIL | -0.0031 | $+1,159.77 | old_thin | late_strong, mid_weak | 16 | +0.0020 |
| 1.075 | FAIL | -0.0074 | $+1,768.96 | old_thin | late_strong, mid_weak | 16 | +0.0030 |
| 1.100 | FAIL | -0.0115 | $+2,456.99 | old_thin | late_strong, mid_weak | 20 | +0.0040 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3700 | -0.0068 | $99,695.99 | $100,003.07 | $+307.08 | 0.8039 | 2 |
| mid_weak | 1.6788 | 1.6788 | +0.0000 | $62,644.67 | $62,644.67 | $+0.00 | 0.7925 | 4 |
| old_thin | 0.4292 | 0.4361 | +0.0069 | $31,563.29 | $31,827.49 | $+264.20 | 0.9167 | 5 |

Production impact: replay-only scout unless Gate 4 passes and the same state is promoted into shared `portfolio_engine.py` code with attribution parity. The state fields are already produced by shared `risk_engine.py`.
