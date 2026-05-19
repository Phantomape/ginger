# exp-20260514-004 Core Borderline Exec-RR Haircut

Decision: `rejected_core_borderline_exec_rr_haircut`.

Single variable: post-sizing risk haircut for already-qualified `trend_long` and `breakout_long` non-ETF/non-commodity stock signals with `1.20 <= exec_lag_adj_net_rr < 1.80`. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.50 | FAIL | -0.2102 | $-2,288.05 | old_thin | late_strong | 2 | +0.0000 |
| 0.75 | FAIL | -0.1055 | $-1,169.05 | old_thin | late_strong | 2 | +0.0000 |
| 0.90 | FAIL | -0.0412 | $-458.37 | old_thin | late_strong | 2 | +0.0000 |

Selected multiplier: `0.9`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3302 | -0.0466 | $99,695.99 | $99,085.90 | $-610.09 | 0.8039 | 1 |
| mid_weak | 1.6788 | 1.6788 | +0.0000 | $62,644.67 | $62,644.67 | $+0.00 | 0.7925 | 0 |
| old_thin | 0.4292 | 0.4346 | +0.0054 | $31,563.29 | $31,715.01 | $+151.72 | 0.9167 | 1 |

Production impact: replay-only scout. A positive result must be promoted through shared `risk_engine.py` / `portfolio_engine.py` code and attribution-key parity before production-visible behavior changes.
