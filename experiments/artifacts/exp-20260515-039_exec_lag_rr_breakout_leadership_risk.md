# exp-20260515-039 Exec-Lag R:R Breakout Leadership Risk

Decision: `rejected_exec_lag_rr_breakout_leadership_risk`.

Single variable: cap-aware post-sizing risk top-up for already-qualified non-ETF/non-commodity `breakout_long` signals whose `exec_lag_adj_net_rr` is in the same-day breakout top quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and existing sizing rules were unchanged.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | +0.0085 | $+200.87 | late_strong | mid_weak | 13 | +0.0004 |
| 1.0250 | FAIL | +0.0074 | $+438.19 | late_strong | mid_weak | 13 | +0.0010 |
| 1.0500 | FAIL | +0.0045 | $+906.30 | late_strong | mid_weak | 14 | +0.0020 |
| 1.0750 | FAIL | +0.0137 | $+1,377.59 | late_strong | mid_weak | 14 | +0.0030 |
| 1.1000 | FAIL | +0.0009 | $+1,609.46 | late_strong | mid_weak | 16 | +0.0040 |

Selected multiplier: `1.075`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1204 | +0.0140 | $116,319.10 | $117,706.32 | $+1,387.22 | 0.0695 | 0.8039 | 4 |
| mid_weak | 2.0987 | 2.0984 | -0.0003 | $76,035.04 | $76,028.68 | $-6.36 | 0.1063 | 0.7925 | 6 |
| old_thin | 0.5294 | 0.5294 | +0.0000 | $37,282.59 | $37,279.32 | $-3.27 | 0.1001 | 0.8667 | 4 |

Production impact: replay-only scout. A passing result must be promoted through shared risk/sizing policy and parity tests before production-visible behavior changes.
