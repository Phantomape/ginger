# exp-20260514-029 Risk-On Unmodified Cap

Decision: `rejected_risk_on_unmodified_cap`.

Single variable: max position cap for non-SPY-relative signals that already qualify for the otherwise-unmodified risk-on sizing path. Entries, exits, ranking, universe, LLM/news logic, accepted risk multipliers, heat, and slot limits were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.450 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 0.500 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| 0.550 | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |

Selected cap: `0.45`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.4853 | +0.0000 | $103,112.67 | $103,112.67 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.8502 | 1.8502 | +0.0000 | $68,776.24 | $68,776.24 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.4704 | 0.4704 | +0.0000 | $33,597.15 | $33,597.15 | $+0.00 | +0.0000 | 0.9167 | 0 |

Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.
