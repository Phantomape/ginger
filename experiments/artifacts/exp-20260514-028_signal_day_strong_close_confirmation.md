# exp-20260514-028 Signal-Day Strong-Close Confirmation

Decision: `rejected_signal_day_strong_close_confirmation`.

Single variable: replace the accepted signal-day green-candle top-up state with a same-scalar close-location confirmation state. No entries, ranking, exits, universe, LLM/news, heat, slots, or other sizing rules changed.

## Sweep

| Close-location min | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.70 | FAIL | -0.0553 | $-1,381.48 | - | late_strong, old_thin | 33 | +0.0000 |
| 0.75 | FAIL | -0.0559 | $-1,381.47 | mid_weak | late_strong, old_thin | 30 | +0.0000 |
| 0.80 | FAIL | -0.0552 | $-1,335.67 | mid_weak | late_strong, old_thin | 25 | +0.0000 |
| 0.90 | FAIL | -0.0650 | $-2,168.53 | - | late_strong, mid_weak, old_thin | 14 | +0.0000 |

Selected close-location min: `0.8`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.4411 | -0.0442 | $103,112.67 | $102,331.96 | $-780.71 | -0.0002 | 0.8039 | 8 |
| mid_weak | 1.8502 | 1.8505 | +0.0003 | $68,776.24 | $68,791.59 | $+15.35 | +0.0000 | 0.7925 | 7 |
| old_thin | 0.4704 | 0.4591 | -0.0113 | $33,597.15 | $33,026.84 | $-570.31 | +0.0000 | 0.9167 | 10 |

Production impact: shadow scout only unless promoted into shared `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py`, and sizing attribution tests.
