# exp-20260514-022 Core Token-Risk Floor

Decision: `rejected_core_token_risk_floor`.

Single variable: minimum post-sizing actual `risk_pct` for core `trend_long`/`breakout_long` entries. Positive but token-sized residual risk below the floor is set to zero shares after existing shared sizing helpers run. Entries, ranking, exits, targets, universe, LLM/news, caps, and heat are locked.

## Sweep

| Risk floor | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Trades after | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|---:|
| 0.0010 | FAIL | +0.2398 | $-5,262.21 | late_strong, mid_weak | old_thin | 16 | 55 | +0.0000 |
| 0.0025 | FAIL | +0.2398 | $-5,262.21 | late_strong, mid_weak | old_thin | 17 | 55 | +0.0000 |
| 0.0050 | FAIL | -1.0421 | $-29,842.10 | - | late_strong, mid_weak, old_thin | 31 | 55 | +0.0001 |

Selected risk floor: `0.001`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4313 | 4.4322 | +0.0009 | $101,873.18 | $101,894.11 | $+20.93 | 18 | 0.8039 | 3 |
| mid_weak | 1.7334 | 2.0422 | +0.3088 | $65,410.59 | $63,030.20 | $-2,380.39 | 17 | 0.7818 | 6 |
| old_thin | 0.4520 | 0.3821 | -0.0699 | $32,522.26 | $29,619.51 | $-2,902.75 | 20 | 0.9333 | 7 |

Production impact: replay-only scout unless Gate 4 passes and the same floor is promoted into shared `portfolio_engine` sizing with attribution parity.
