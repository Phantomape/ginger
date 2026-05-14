# exp-20260514-012 Non-Financials Sector-Relative Leader Risk

Decision: `rejected_core_nonfinancial_sector_relative_leader_risk`.

Single variable: cap-aware post-sizing risk top-up for already-qualified `trend_long` and `breakout_long` non-ETF/non-commodity/non-Financials stock signals whose 20d return is above their equal-weight same-sector 20d return. No entry filter, ranking, exit, target, universe, LLM, news, or portfolio heat behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | -0.0010 | $+526.82 | old_thin | late_strong | 20 | +0.0013 |
| 1.050 | FAIL | -0.0062 | $+981.00 | old_thin | late_strong, mid_weak | 26 | +0.0027 |
| 1.100 | FAIL | -0.0176 | $+2,045.95 | mid_weak, old_thin | late_strong | 29 | +0.0060 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3739 | -0.0029 | $99,695.99 | $100,086.95 | $+390.96 | 0.8039 | 6 |
| mid_weak | 1.6788 | 1.6788 | +0.0000 | $62,644.67 | $62,642.55 | $-2.12 | 0.7925 | 6 |
| old_thin | 0.4292 | 0.4311 | +0.0019 | $31,563.29 | $31,701.27 | $+137.98 | 0.9167 | 8 |

Production impact: replay-only scout unless Gate 4 passes and the same state is promoted into shared `risk_engine.py` and `portfolio_engine.py` code with parity tests.
