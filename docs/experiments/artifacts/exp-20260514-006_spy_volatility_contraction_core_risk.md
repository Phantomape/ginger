# exp-20260514-006 SPY Volatility-Contraction Core Risk

Decision: `rejected_spy_volatility_contraction_core_risk`.

Single variable: cap-aware post-sizing risk top-up for already-qualified `trend_long` and `breakout_long` non-ETF/non-commodity stock signals when SPY 20d realized volatility is below SPY 60d realized volatility. No entry filter, ranking, exit, target, universe, LLM, news, or portfolio heat behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | -0.0071 | $+518.48 | mid_weak | late_strong | 12 | +0.0013 |
| 1.050 | FAIL | -0.0172 | $+1,200.91 | - | late_strong, mid_weak | 15 | +0.0033 |
| 1.100 | FAIL | -0.0237 | $+2,621.75 | mid_weak, old_thin | late_strong | 19 | +0.0070 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3696 | -0.0072 | $99,695.99 | $99,987.58 | $+291.59 | 0.8039 | 2 |
| mid_weak | 1.6788 | 1.6789 | +0.0001 | $62,644.67 | $62,878.93 | $+234.26 | 0.7925 | 7 |
| old_thin | 0.4292 | 0.4292 | +0.0000 | $31,563.29 | $31,555.92 | $-7.37 | 0.9167 | 3 |

Production impact: replay-only scout unless Gate 4 passes and the same state is promoted into shared `feature_layer.py`, `risk_engine.py`, and `portfolio_engine.py` code with parity tests.
