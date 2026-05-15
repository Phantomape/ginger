# exp-20260515-013 Clean-SPY Cap-Only RS20 Cap

Decision: `accepted_promoted_shared_policy`.

Single variable: max position cap for already-qualified clean-SPY cap-only leaders that also have `rs20_entry_state_leader=true`. Entries, exits, ranking, universe, LLM/news logic, raw risk multipliers, heat, and slots were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.625 | PASS | +0.0878 | $+2,067.11 | late_strong, mid_weak, old_thin | - | 10 | +0.0008 |
| 0.650 | PASS | +0.1972 | $+4,380.94 | late_strong, mid_weak, old_thin | - | 10 | +0.0015 |
| 0.675 | PASS | +0.2937 | $+6,630.33 | late_strong, mid_weak, old_thin | - | 10 | +0.0022 |
| 0.700 | PASS | +0.3865 | $+8,878.68 | late_strong, mid_weak, old_thin | - | 10 | +0.0030 |

Selected cap: `0.7`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.7144 | 5.0322 | +0.3178 | $107,875.49 | $114,886.19 | $+7,010.70 | +0.0030 | 0.8039 | 5 |
| mid_weak | 1.9376 | 1.9947 | +0.0571 | $71,496.04 | $72,796.75 | $+1,300.71 | +0.0000 | 0.7925 | 1 |
| old_thin | 0.4943 | 0.5059 | +0.0116 | $34,812.38 | $35,379.65 | $+567.27 | +0.0016 | 0.9167 | 4 |

Production impact: promoted through shared `constants.py`, `portfolio_engine.py`, `backtester.py`, and focused production-parity tests.
