# exp-20260513-018 Core Confirmed Quality Risk

Decision: `rejected_core_confirmed_quality_risk`.

Single variable: cap-aware post-sizing risk top-up for core `trend_long` and `breakout_long` signals with `trade_quality_score >= 0.95`, `rs20_entry_state_leader=true`, and `signal_day_ticker_green_candle=true`. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.05 | FAIL | +0.0215 | $+1,141.34 | late_strong, old_thin | mid_weak | 18 | +0.0033 |
| 1.06 | FAIL | +0.0236 | $+1,433.00 | late_strong, old_thin | mid_weak | 18 | +0.0045 |
| 1.07 | FAIL | +0.0291 | $+1,606.19 | late_strong, old_thin | mid_weak | 18 | +0.0049 |
| 1.08 | FAIL | +0.0390 | $+1,996.38 | late_strong, mid_weak, old_thin | - | 18 | +0.0057 |
| 1.09 | FAIL | +0.0369 | $+2,127.92 | late_strong, old_thin | mid_weak | 18 | +0.0062 |
| 1.10 | FAIL | +0.0449 | $+2,450.85 | late_strong, mid_weak, old_thin | - | 19 | +0.0070 |
| 1.15 | FAIL | +0.0509 | $+3,550.73 | late_strong, mid_weak, old_thin | - | 22 | +0.0106 |
| 1.20 | FAIL | +0.0534 | $+4,540.10 | late_strong, mid_weak, old_thin | - | 26 | +0.0142 |

Selected multiplier: `1.2`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 4.3233 | +0.0339 | $95,321.74 | $95,860.78 | $+539.04 | 0.8039 | 4 |
| mid_weak | 1.6747 | 1.6785 | +0.0038 | $62,490.66 | $65,314.84 | $+2,824.18 | 0.7925 | 10 |
| old_thin | 0.3867 | 0.4024 | +0.0157 | $28,855.61 | $30,032.49 | $+1,176.88 | 0.9167 | 12 |

Production impact: replay-only scout. Positive promotion requires shared `portfolio_engine` attribution and production parity coverage before live/default behavior changes.
