# exp-20260514-054 Technology Breakout Persistent-Leader Cap

Decision: `rejected_tech_breakout_persistent_leader_cap`.

Single variable: max position cap for already-qualified `breakout_long` Technology signals with `rs60_top_quintile_state=true`, `signal_day_ticker_outperformed_spy=true`, and active clean-SPY leader sizing. Entries, exits, ranking, universe, LLM/news logic, heat, and slots were unchanged.

## Sweep

| Cap | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.550 | FAIL | -0.2664 | $+3,828.84 | - | late_strong | 6 | +0.0216 |
| 0.575 | FAIL | -0.2865 | $+4,694.36 | - | late_strong | 6 | +0.0245 |
| 0.600 | FAIL | -0.3083 | $+5,551.95 | - | late_strong | 6 | +0.0273 |

Selected cap: `0.55`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5715 | 4.3051 | -0.2664 | $104,612.99 | $108,441.83 | $+3,828.84 | +0.0216 | 0.8039 | 2 |
| mid_weak | 1.9019 | 1.9019 | +0.0000 | $70,437.12 | $70,437.12 | $+0.00 | +0.0000 | 0.7925 | 2 |
| old_thin | 0.4920 | 0.4920 | +0.0000 | $34,645.58 | $34,645.58 | $+0.00 | +0.0000 | 0.9167 | 2 |

Production impact: shadow scout only. Positive promotion would require shared `portfolio_engine` cap policy plus attribution/parity tests before live/default behavior changes.
