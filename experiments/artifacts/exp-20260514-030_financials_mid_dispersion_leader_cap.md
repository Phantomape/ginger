# exp-20260514-030 Financials Mid-Dispersion Leader Cap

Decision: `accepted_shared_policy_promoted`.

Single variable: max position cap for the already-accepted `trend_long + Financials + financials_sector_leader=true` sleeve, restricted to signals that also carry `mid_sector_dispersion=true`. Entries, exits, ranking, universe, LLM/news logic, raw multipliers, heat, and slot limits were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.525 | PASS | +0.0067 | $+351.45 | mid_weak, old_thin | - | 3 | +0.0007 |
| 0.550 | PASS | +0.0123 | $+618.16 | mid_weak, old_thin | - | 3 | +0.0013 |

Selected cap: `0.55`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.4853 | +0.0000 | $103,112.67 | $103,112.67 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 1.8502 | 1.8580 | +0.0078 | $68,776.24 | $69,070.09 | $+293.85 | +0.0001 | 0.7925 | 1 |
| old_thin | 0.4704 | 0.4749 | +0.0045 | $33,597.15 | $33,921.46 | $+324.31 | +0.0013 | 0.9167 | 2 |

Production impact: promoted into shared `constants.py` and `portfolio_engine.py`; `backtester.py` records the sizing attribution key; production and backtest both call the same shared `size_signals` path. Focused sizing and parity tests passed.
