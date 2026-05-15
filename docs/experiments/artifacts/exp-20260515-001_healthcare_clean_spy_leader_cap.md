# exp-20260515-001 Healthcare Clean-SPY Leader Cap

Decision: `rejected_healthcare_clean_spy_leader_cap`.

Single variable: max-position cap for already-qualified Healthcare trend/breakout signals with active clean-SPY leader sizing. No entry filter, ranking, exit, target, universe, LLM, news, heat, or slot behavior changed.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.550 | FAIL | +0.0031 | $+90.88 | late_strong | old_thin | 2 | +0.0000 |
| 0.575 | FAIL | +0.0256 | $+307.22 | late_strong | old_thin | 2 | +0.0000 |
| 0.600 | FAIL | +0.0551 | $+661.58 | late_strong | old_thin | 2 | +0.0001 |

## Selected Candidate

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5715 | 4.6341 | +0.0626 | $104,612.99 | $105,557.12 | $+944.13 | -0.0002 | 0.8039 | 1 |
| mid_weak | 1.9019 | 1.9019 | +0.0000 | $70,437.12 | $70,437.12 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.4920 | 0.4845 | -0.0075 | $34,645.58 | $34,363.03 | $-282.55 | +0.0001 | 0.9167 | 1 |

Production impact: shadow scout only. Positive promotion requires a shared `portfolio_engine` policy plus attribution/parity tests before live/default behavior changes.
