# exp-20260514-037 RS20 Entry-State Leader Cap

Decision: `rejected_rs20_entry_state_leader_cap`.

Single variable: max-position cap available to existing `rs20_entry_state_leader=true` trend/breakout signals. RS20 scalar, entries, exits, ranking, universe, LLM/news, heat, slots, and every other sizing rule stayed fixed.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.550 | FAIL | -0.0870 | $+9,556.76 | mid_weak, old_thin | late_strong | 45 | +0.0226 |
| 0.600 | FAIL | +0.1242 | $+19,137.37 | late_strong, mid_weak, old_thin | - | 48 | +0.0295 |

Selected cap: `0.6`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.4877 | +0.0024 | $103,112.67 | $115,070.57 | $+11,957.90 | +0.0295 | 0.8039 | 16 |
| mid_weak | 1.8580 | 1.9111 | +0.0531 | $69,070.09 | $70,777.59 | $+1,707.50 | +0.0001 | 0.7925 | 11 |
| old_thin | 0.4749 | 0.5436 | +0.0687 | $33,921.46 | $39,393.43 | $+5,471.97 | +0.0170 | 0.8667 | 21 |

Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.
