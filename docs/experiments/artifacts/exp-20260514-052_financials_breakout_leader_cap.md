# exp-20260514-052 Financials Breakout Sector-Leader Cap

Decision: `rejected_financials_breakout_leader_cap`.

Single variable: max position cap for already-qualified `breakout_long` Financials signals with `financials_sector_leader=true`. Entries, exits, ranking, universe, LLM/news logic, earnings DTE multiplier, heat, and slots were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.500 | FAIL | -0.0011 | $-41.20 | - | mid_weak | 1 | +0.0000 |
| 0.525 | FAIL | -0.0011 | $-41.20 | - | mid_weak | 1 | +0.0000 |
| 0.550 | FAIL | +0.0003 | $+60.66 | old_thin | mid_weak | 2 | +0.0000 |

Selected cap: `0.55`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5715 | 4.5715 | +0.0000 | $104,612.99 | $104,612.99 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.9019 | 1.9008 | -0.0011 | $70,437.12 | $70,395.92 | $-41.20 | +0.0000 | 0.7925 | 1 |
| old_thin | 0.4920 | 0.4934 | +0.0014 | $34,645.58 | $34,747.44 | $+101.86 | +0.0000 | 0.9167 | 1 |

Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.
