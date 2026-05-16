# exp-20260516-027 Non-Consumer Signal-Day ATR Expansion Top-Up

Decision: `rejected_signal_day_atr_expansion_nonconsumer_topup`.

Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout signals whose signal-day `atr_expansion` is in the same-day top quartile after excluding ETF, Commodities, Consumer Discretionary, and Communication Services. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0125 | no | FAIL | +0.0015 | $+417.01 | mid_weak | late_strong | 17 | late_strong, mid_weak, old_thin | +0.0004 |
| 1.0250 | no | FAIL | +0.0117 | $+1,081.62 | mid_weak | late_strong | 21 | late_strong, mid_weak, old_thin | +0.0016 |
| 1.0500 | no | FAIL | +0.0263 | $+2,126.06 | mid_weak | late_strong | 25 | late_strong, mid_weak, old_thin | +0.0036 |
| 1.0750 | no | FAIL | +0.0133 | $+2,611.31 | mid_weak | late_strong | 25 | late_strong, mid_weak, old_thin | +0.0052 |

Selected non-control multiplier: `1.05`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1286 | -0.0058 | $116,686.40 | $117,364.54 | $+678.14 | +0.0019 | 0.8039 | 7 |
| mid_weak | 2.1054 | 2.1375 | +0.0321 | $76,563.68 | $78,010.55 | $+1,446.87 | +0.0036 | 0.7925 | 10 |
| old_thin | 0.5295 | 0.5295 | +0.0000 | $37,292.45 | $37,293.50 | $+1.05 | +0.0000 | 0.8667 | 8 |

Production impact: replay-only scout. A positive promotion must add shared `risk_engine` ATR-expansion state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.
