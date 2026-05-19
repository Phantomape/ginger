# exp-20260516-046 Signal-Day ATR Compression Risk Scalar

Decision: `rejected_signal_day_atr_compression_risk_scalar`.

Single variable: post-sizing risk scalar for already-qualified trend/breakout stock signals whose signal-day `atr_expansion` is in the same-day non-ETF/non-commodity bottom quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 0.8500 | no | FAIL | -0.0067 | $-520.49 | - | mid_weak | 1 | mid_weak | +0.0000 |
| 0.9000 | no | FAIL | -0.0099 | $-353.44 | - | mid_weak | 1 | mid_weak | +0.0000 |
| 0.9500 | no | FAIL | -0.0049 | $-171.66 | - | mid_weak | 1 | mid_weak | +0.0000 |
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0125 | no | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0250 | no | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0500 | no | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |

Selected non-control multiplier: `1.0125`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1361 | 5.1361 | +0.0000 | $116,727.26 | $116,727.26 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 2.1084 | 2.1084 | +0.0000 | $76,665.80 | $76,665.80 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.5903 | 0.5903 | +0.0000 | $39,615.16 | $39,615.16 | $+0.00 | +0.0000 | 0.8667 | 0 |

Production impact: replay-only scout. A positive promotion must add shared `risk_engine` ATR-compression state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.
