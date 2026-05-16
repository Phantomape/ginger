# exp-20260516-012 Semiconductor Non-Confirming Trend Haircut

Decision: `rejected_semiconductor_nonconfirming_trend_haircut`.

Single variable: post-sizing risk haircut for existing `trend_long` signals in the semiconductor/AI-chip cohort when the ticker's signal-day candle is not green. Candidate set, entry filters, ranking, exits, targets, universe, LLM/news, heat, slots, and other Technology rules were unchanged.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.00 | FAIL | +0.0044 | $+143.90 | late_strong, mid_weak | - | 2 | +0.0000 |
| 0.25 | FAIL | +0.0039 | $+121.76 | late_strong, mid_weak | - | 2 | +0.0000 |
| 0.50 | FAIL | +0.0033 | $+93.95 | late_strong, mid_weak | - | 2 | +0.0000 |
| 0.75 | FAIL | +0.0025 | $+71.82 | late_strong, mid_weak | - | 2 | +0.0000 |

Selected multiplier: `0.0`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1361 | +0.0017 | $116,686.40 | $116,727.26 | $+40.86 | +0.0000 | 0.8039 | 1 |
| mid_weak | 2.1016 | 2.1043 | +0.0027 | $76,421.93 | $76,524.97 | $+103.04 | +0.0000 | 0.7925 | 1 |
| old_thin | 0.5294 | 0.5294 | +0.0000 | $37,282.59 | $37,282.59 | $+0.00 | +0.0000 | 0.8667 | 0 |

Production impact: replay-only scout. Positive promotion requires a shared risk/sizing state, an attribution key, focused parity tests, and the canonical three-window rerun.
