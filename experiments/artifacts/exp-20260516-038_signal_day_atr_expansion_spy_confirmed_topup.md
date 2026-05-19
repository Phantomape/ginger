# exp-20260516-038 SPY-Confirmed Signal-Day ATR Expansion Top-Up

Decision: `rejected_signal_day_atr_expansion_spy_confirmed_topup`.

Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout stock signals whose signal-day `atr_expansion` is in the same-day non-ETF/non-commodity top quartile and whose signal-day open-to-close return beats SPY. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0125 | no | FAIL | +0.0108 | $+272.36 | late_strong, mid_weak | old_thin | 13 | late_strong, mid_weak, old_thin | +0.0004 |
| 1.0250 | no | FAIL | +0.0097 | $+748.61 | late_strong, mid_weak | old_thin | 17 | late_strong, mid_weak, old_thin | +0.0016 |
| 1.0500 | no | FAIL | +0.0103 | $+1,698.92 | late_strong, mid_weak | old_thin | 22 | late_strong, mid_weak, old_thin | +0.0036 |
| 1.0750 | no | FAIL | +0.0145 | $+2,309.64 | late_strong, mid_weak | old_thin | 22 | late_strong, mid_weak, old_thin | +0.0052 |

Selected non-control multiplier: `1.075`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1470 | +0.0126 | $116,686.40 | $118,053.85 | $+1,367.45 | +0.0029 | 0.8039 | 7 |
| mid_weak | 2.1054 | 2.1140 | +0.0086 | $76,563.68 | $77,723.30 | $+1,159.62 | +0.0052 | 0.7925 | 6 |
| old_thin | 0.5295 | 0.5228 | -0.0067 | $37,292.45 | $37,075.02 | $-217.43 | +0.0023 | 0.8667 | 9 |

Production impact: replay-only scout. A positive promotion must add shared `risk_engine` state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.
