# exp-20260514-038 Confirmed RS20 Leader Cap

Decision: `rejected_confirmed_rs20_leader_cap`.

Single variable: max-position cap available only to `rs20_entry_state_leader=true` trend/breakout signals where `signal_day_ticker_outperformed_spy=true`. RS20 scalar, entries, exits, ranking, universe, LLM/news, heat, slots, and every other sizing rule stayed fixed.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.550 | FAIL | -0.1192 | $+8,174.92 | mid_weak, old_thin | late_strong | 32 | +0.0225 |
| 0.600 | FAIL | +0.0517 | $+16,433.76 | mid_weak, old_thin | late_strong | 35 | +0.0296 |

Selected cap: `0.6`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.4327 | -0.0526 | $103,112.67 | $113,661.33 | $+10,548.66 | +0.0296 | 0.8039 | 11 |
| mid_weak | 1.8580 | 1.9121 | +0.0541 | $69,070.09 | $70,824.26 | $+1,754.17 | +0.0001 | 0.7925 | 6 |
| old_thin | 0.4749 | 0.5251 | +0.0502 | $33,921.46 | $38,052.39 | $+4,130.93 | +0.0169 | 0.8667 | 18 |

Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.
