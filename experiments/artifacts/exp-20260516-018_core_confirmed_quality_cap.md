# exp-20260516-018 Core Confirmed-Quality Cap

Decision: `rejected_core_confirmed_quality_cap`.

Single variable: single-position cap for already-qualified `core_confirmed_quality_state=true` signals. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Windows | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---|---:|
| 0.425 | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 0.450 | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 0.475 | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 0.500 | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1344 | +0.0000 | $116,686.40 | $116,686.40 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 2.1016 | 2.1016 | +0.0000 | $76,421.93 | $76,421.93 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.5294 | 0.5294 | +0.0000 | $37,282.59 | $37,282.59 | $+0.00 | +0.0000 | 0.8667 | 0 |
