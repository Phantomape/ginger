# exp-20260514-019 RS60 Top-Quintile Cap

Decision: `rejected_rs60_top_quintile_cap`.

Single variable: max position cap for the already-accepted `rs60_top_quintile_state` stock sleeve. Entries, exits, ranking, universe, LLM/news logic, RS60 risk multiplier, heat, and slot limits were unchanged.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4313 | 4.3755 | -0.0558 | $101,873.18 | $105,179.21 | $+3,306.03 | +0.0108 | 0.8039 | 2 |
| mid_weak | 1.7334 | 1.7910 | +0.0576 | $65,410.59 | $66,826.86 | $+1,416.27 | +0.0000 | 0.7925 | 6 |
| old_thin | 0.4520 | 0.4497 | -0.0023 | $32,522.26 | $32,593.99 | $+71.73 | +0.0014 | 0.9167 | 4 |

## Sweep

| Cap | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |
|---:|---|---:|---:|---:|---:|
| 0.45 | FAIL | -0.0005 | $+4,794.03 | +0.0108 | 12 |
| 0.50 | FAIL | -0.0232 | $+7,810.54 | +0.0167 | 14 |

Production impact: shadow experiment only unless promoted into shared `constants.py` and `portfolio_engine.py`. A positive promotion must apply the cap before both backtest and production paths call `size_signals`.
