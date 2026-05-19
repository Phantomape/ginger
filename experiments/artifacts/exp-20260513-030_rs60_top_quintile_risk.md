# exp-20260513-030 RS60 Top-Quintile Risk

Decision: `accepted_shared_policy_implemented`.

Single variable: cap-aware post-sizing risk top-up for `trend_long` and `breakout_long` stock signals whose same-day 60-trading-day return is in the top quintile of the non-ETF/non-commodity stock universe. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.05 | FAIL | +0.0489 | $+1,638.93 | late_strong, old_thin | mid_weak | 21 | +0.0004 |
| 1.10 | FAIL | +0.0958 | $+3,203.27 | late_strong, old_thin | mid_weak | 23 | +0.0009 |
| 1.15 | PASS | +0.1094 | $+4,615.93 | late_strong, mid_weak, old_thin | - | 27 | +0.0016 |
| 1.20 | PASS | +0.0995 | $+5,559.34 | late_strong, mid_weak, old_thin | - | 31 | +0.0029 |

Selected multiplier: `1.15`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3663 | +0.0769 | $95,321.74 | $98,115.26 | $+2,793.52 | 0.8039 | 7 |
| mid_weak | 1.6747 | 1.6788 | +0.0041 | $62,490.66 | $62,644.67 | $+154.01 | 0.7925 | 10 |
| old_thin | 0.3867 | 0.4151 | +0.0284 | $28,855.61 | $30,524.01 | $+1,668.40 | 0.9167 | 10 |

Production impact: accepted shared policy. `feature_layer.py`, `risk_engine.py`, and `portfolio_engine.py` implement the state and cap-aware top-up; `backtester.py` records attribution for the same shared sizing key.
