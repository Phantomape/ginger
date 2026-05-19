# exp-20260516-026 Signal-Day ATR Expansion Top-Up

Decision: `rejected_signal_day_atr_expansion_topup`.

Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout stock signals whose signal-day `atr_expansion` is in the same-day non-ETF/non-commodity top quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0125 | no | FAIL | +0.0115 | $+417.78 | late_strong, mid_weak | old_thin | 21 | late_strong, mid_weak, old_thin | +0.0009 |
| 1.0250 | no | FAIL | +0.0242 | $+1,090.27 | late_strong, mid_weak | old_thin | 25 | late_strong, mid_weak, old_thin | +0.0018 |
| 1.0500 | no | FAIL | +0.0321 | $+2,142.98 | late_strong, mid_weak | old_thin | 30 | late_strong, mid_weak, old_thin | +0.0036 |
| 1.0750 | no | FAIL | +0.0286 | $+2,564.65 | late_strong, mid_weak | old_thin | 30 | late_strong, mid_weak, old_thin | +0.0054 |

Selected non-control multiplier: `1.05`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1422 | +0.0078 | $116,686.40 | $117,673.20 | $+986.80 | +0.0019 | 0.8039 | 8 |
| mid_weak | 2.1054 | 2.1375 | +0.0321 | $76,563.68 | $78,010.55 | $+1,446.87 | +0.0036 | 0.7925 | 11 |
| old_thin | 0.5295 | 0.5217 | -0.0078 | $37,292.45 | $37,001.76 | $-290.69 | +0.0036 | 0.8667 | 11 |

Production impact: replay-only scout. A positive promotion must add shared `risk_engine` ATR-expansion state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.
