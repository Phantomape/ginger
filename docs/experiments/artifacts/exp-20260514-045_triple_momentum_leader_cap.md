# exp-20260514-045 Triple Momentum Leader Cap

Decision: `rejected_triple_momentum_leader_cap`.

Single variable: max-position cap available only to `rs20_entry_state_leader=true`, `rs60_top_quintile_state=true`, and `signal_day_ticker_green_candle=true` trend/breakout signals. Entries, exits, ranking, universe, LLM/news, heat, slots, and every other sizing rule stayed fixed.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.500 | FAIL | +0.0229 | $+286.74 | late_strong | - | 1 | +0.0000 |
| 0.525 | FAIL | +0.0181 | $+178.21 | late_strong | - | 2 | +0.0000 |
| 0.550 | FAIL | -0.1639 | $+8,078.41 | old_thin | late_strong | 15 | +0.0225 |

Selected cap: `0.5`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4853 | 4.5082 | +0.0229 | $103,112.67 | $103,399.41 | $+286.74 | +0.0000 | 0.8039 | 1 |
| mid_weak | 1.8580 | 1.8580 | +0.0000 | $69,070.09 | $69,070.09 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.4749 | 0.4749 | +0.0000 | $33,921.46 | $33,921.46 | $+0.00 | +0.0000 | 0.9167 | 0 |

Production impact: shadow scout only unless promoted into shared `constants.py`, `portfolio_engine.py`, backtest attribution, and focused parity tests.
