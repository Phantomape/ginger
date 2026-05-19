# exp-20260514-049 Commodity Breakout Cap

Decision: `accepted_for_shared_policy_implementation`.

Single variable: max position cap for already-qualified `breakout_long` signals in the `Commodities` sector. Entries, exits, ranking, universe, LLM/news logic, raw multipliers, heat, slots, and accepted Commodity trend near-high rules were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.525 | FAIL | +0.0317 | $+490.67 | late_strong | - | 3 | +0.0000 |
| 0.550 | PASS | +0.0681 | $+1,295.14 | late_strong, mid_weak | - | 5 | +0.0000 |
| 0.575 | PASS | +0.1092 | $+2,119.18 | late_strong, mid_weak | - | 5 | +0.0000 |

Selected cap: `0.575`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.5701 | +0.0848 | $103,112.67 | $104,582.95 | $+1,470.28 | -0.0003 | 0.8039 | 2 |
| mid_weak | 1.8580 | 1.8824 | +0.0244 | $69,070.09 | $69,718.99 | $+648.90 | +0.0000 | 0.7925 | 2 |
| old_thin | 0.4749 | 0.4749 | +0.0000 | $33,921.46 | $33,921.46 | $+0.00 | +0.0000 | 0.9167 | 1 |

Production impact: promoted through shared `constants.py` and `portfolio_engine.py`; `quant/run.py` and `quant/backtester.py` both use the same sizing helper, backtest attribution includes `breakout_commodities_max_position_pct_applied`, and focused parity tests cover the rule.
