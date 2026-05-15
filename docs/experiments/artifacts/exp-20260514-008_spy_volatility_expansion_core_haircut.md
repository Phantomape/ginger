# exp-20260514-008 SPY Volatility-Expansion Core Haircut

Decision: `rejected_spy_volatility_expansion_core_haircut`.

Single variable: post-sizing risk haircut for already-qualified `trend_long` and `breakout_long` non-ETF/non-commodity stock signals when SPY 20d realized volatility is above SPY 60d realized volatility. No entry filter, ranking, exit, target, universe, LLM, news, or portfolio heat behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.500 | FAIL | -1.2227 | $-24,655.42 | mid_weak | late_strong, old_thin | 32 | +0.0004 |
| 0.750 | FAIL | -0.5506 | $-10,968.54 | mid_weak | late_strong, old_thin | 32 | +0.0003 |
| 0.900 | FAIL | -0.2115 | $-4,228.43 | mid_weak | late_strong, old_thin | 32 | +0.0000 |

Selected multiplier: `0.9`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.1783 | -0.1985 | $99,695.99 | $96,719.60 | $-2,976.39 | 0.8039 | 10 |
| mid_weak | 1.6788 | 1.6804 | +0.0016 | $62,644.67 | $62,699.92 | $+55.25 | 0.7925 | 2 |
| old_thin | 0.4292 | 0.4146 | -0.0146 | $31,563.29 | $30,256.00 | $-1,307.29 | 0.9167 | 20 |

Production impact: replay-only scout unless Gate 4 passes and the same state is promoted into shared `feature_layer.py`, `risk_engine.py`, and `portfolio_engine.py` code with parity tests.
