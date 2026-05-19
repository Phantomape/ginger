# exp-20260515-024 Price Extension Nonconfirmation Haircut

Decision: `rejected_price_extension_nonconfirmation_haircut`.

Single variable: post-sizing haircut for already-qualified trend/breakout non-ETF/non-commodity stocks with `price_vs_200ma_extension_state=true` and `signal_day_ticker_outperformed_spy=false`.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 0.9750 | FAIL | -0.0476 | $-844.82 | - | late_strong, mid_weak, old_thin | 10 | +0.0000 |
| 0.9500 | FAIL | -0.0822 | $-1,664.02 | - | late_strong, mid_weak, old_thin | 10 | +0.0000 |
| 0.9000 | FAIL | -0.1461 | $-3,079.32 | old_thin | late_strong, mid_weak | 10 | +0.0000 |
| 0.8500 | FAIL | -0.2295 | $-4,564.86 | old_thin | late_strong, mid_weak | 10 | +0.0001 |
| 0.7500 | FAIL | -0.3743 | $-7,503.32 | old_thin | late_strong, mid_weak | 10 | +0.0000 |

Selected multiplier: `0.975`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0334 | 5.0044 | -0.0290 | $115,183.05 | $114,777.92 | $-405.13 | 0.0665 | 0.8039 | 1 |
| mid_weak | 2.0103 | 1.9925 | -0.0178 | $73,104.97 | $72,719.16 | $-385.81 | 0.1014 | 0.7925 | 5 |
| old_thin | 0.5099 | 0.5091 | -0.0008 | $35,657.24 | $35,603.36 | $-53.88 | 0.0924 | 0.9167 | 4 |

Production impact: replay-only scout. Positive promotion requires the helper in shared `portfolio_engine.py`, attribution keys in `backtester.py`, docs parity update, and focused parity tests before live/default behavior changes.
