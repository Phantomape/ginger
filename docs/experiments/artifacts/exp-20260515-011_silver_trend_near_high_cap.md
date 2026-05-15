# exp-20260515-011 Silver Trend Near-High Cap

Decision: `rejected_silver_trend_near_high_cap`.

Single variable: max position cap for already-qualified `SLV` `trend_long` signals in the accepted `Commodities` near-52-week-high sleeve. Entries, exits, ranking, universe, LLM/news logic, target width, raw Commodity multiplier, heat, and slots were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.575 | FAIL | +0.0003 | $+18.22 | mid_weak | - | 1 | +0.0001 |
| 0.600 | FAIL | +0.0003 | $+18.22 | mid_weak | - | 1 | +0.0001 |
| 0.625 | FAIL | +0.0003 | $+18.22 | mid_weak | - | 1 | +0.0001 |
| 0.650 | FAIL | +0.0003 | $+18.22 | mid_weak | - | 1 | +0.0001 |

Selected cap: `0.575`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.7144 | 4.7144 | +0.0000 | $107,875.49 | $107,875.49 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.9376 | 1.9379 | +0.0003 | $71,496.04 | $71,514.26 | $+18.22 | +0.0001 | 0.7925 | 1 |
| old_thin | 0.4943 | 0.4943 | +0.0000 | $34,812.38 | $34,812.38 | $+0.00 | +0.0000 | 0.9167 | 0 |

Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.
