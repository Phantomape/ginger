# exp-20260514-050 Gold Trend Near-High Cap

Decision: `accepted_for_shared_policy_implementation`.

Single variable: max position cap for already-qualified `trend_long` Gold (`GLD`/`IAU`) signals that already carry the accepted Commodity near-high sleeve. Entries, exits, ranking, universe, LLM/news logic, raw Commodity multipliers, SLV, heat, and slots were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.525 | PASS | +0.0152 | $+531.56 | late_strong, mid_weak, old_thin | - | 5 | +0.0003 |
| 0.550 | PASS | +0.0244 | $+991.05 | late_strong, mid_weak, old_thin | - | 5 | +0.0006 |
| 0.575 | PASS | +0.0380 | $+1,472.29 | late_strong, mid_weak, old_thin | - | 5 | +0.0009 |

Selected cap: `0.575`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5701 | 4.5715 | +0.0014 | $104,582.95 | $104,612.99 | $+30.04 | +0.0000 | 0.8039 | 2 |
| mid_weak | 1.8824 | 1.9019 | +0.0195 | $69,718.99 | $70,437.12 | $+718.13 | +0.0000 | 0.7925 | 2 |
| old_thin | 0.4749 | 0.4920 | +0.0171 | $33,921.46 | $34,645.58 | $+724.12 | +0.0009 | 0.9167 | 1 |

Production impact: promoted into shared `constants.py` and `portfolio_engine.py`, exposed through backtest sizing attribution, and covered by focused parity tests. `run.py` and `backtester.py` both call the same shared sizing module; this is not a replay-only policy.
