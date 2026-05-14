# exp-20260513-113 High Exec-RR Core Risk

Decision: `rejected_high_exec_rr_core_risk`.

Single variable: cap-aware post-sizing risk top-up for already-qualified `trend_long` and `breakout_long` non-ETF/non-commodity stock signals whose `exec_lag_adj_net_rr` clears the selected high-quality boundary. No entry filter, ranking, exit, target, universe, LLM, news, or portfolio heat behavior changed.

## Sweep

| Exec RR Min | Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|---:|:---:|---:|---:|---|---|---:|---:|
| 1.80 | 1.05 | FAIL | -0.0083 | $+1,606.95 | old_thin | late_strong, mid_weak | 32 | +0.0033 |
| 1.80 | 1.10 | FAIL | -0.0121 | $+3,437.70 | mid_weak, old_thin | late_strong | 37 | +0.0070 |
| 1.80 | 1.15 | FAIL | -0.0334 | $+4,797.42 | mid_weak, old_thin | late_strong | 41 | +0.0106 |
| 2.00 | 1.05 | FAIL | -0.0083 | $+1,606.95 | old_thin | late_strong, mid_weak | 32 | +0.0033 |
| 2.00 | 1.10 | FAIL | -0.0121 | $+3,437.70 | mid_weak, old_thin | late_strong | 37 | +0.0070 |
| 2.00 | 1.15 | FAIL | -0.0334 | $+4,797.42 | mid_weak, old_thin | late_strong | 41 | +0.0106 |
| 2.20 | 1.05 | FAIL | -0.0081 | $+1,610.22 | old_thin | late_strong, mid_weak | 30 | +0.0033 |
| 2.20 | 1.10 | FAIL | -0.0119 | $+3,447.21 | mid_weak, old_thin | late_strong | 34 | +0.0070 |
| 2.20 | 1.15 | FAIL | -0.0313 | $+4,852.12 | mid_weak, old_thin | late_strong | 37 | +0.0106 |

Selected parameters: `exec_lag_adj_net_rr >= 2.2` and `1.05x` top-up.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3670 | -0.0098 | $99,695.99 | $100,387.81 | $+691.82 | 0.8039 | 8 |
| mid_weak | 1.6788 | 1.6761 | -0.0027 | $62,644.67 | $63,250.36 | $+605.69 | 0.7925 | 10 |
| old_thin | 0.4292 | 0.4336 | +0.0044 | $31,563.29 | $31,876.00 | $+312.71 | 0.9167 | 12 |

Production impact: replay-only scout. A positive result must be promoted through shared `risk_engine.py` / `portfolio_engine.py` code and attribution-key parity before production-visible behavior changes.
