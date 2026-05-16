# exp-20260516-022 Signal-Day ATR Expansion Risk

Decision: `rejected_signal_day_atr_expansion_risk`.

Single variable: post-sizing risk multiplier for already-qualified trend/breakout stock signals whose signal-day `atr_expansion` is in the same-day non-ETF/non-commodity top quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 0.850 | no | FAIL | -0.6876 | $-21,668.73 | - | late_strong, mid_weak, old_thin | 69 | late_strong, mid_weak, old_thin | -0.0096 |
| 0.900 | no | FAIL | -0.4780 | $-14,818.89 | - | late_strong, mid_weak, old_thin | 69 | late_strong, mid_weak, old_thin | -0.0062 |
| 0.950 | no | FAIL | -0.2491 | $-7,691.73 | - | late_strong, mid_weak, old_thin | 69 | late_strong, mid_weak, old_thin | -0.0033 |
| 1.000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |

Selected non-control multiplier: `0.95`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 4.9502 | -0.1842 | $116,686.40 | $112,245.19 | $-4,441.21 | -0.0033 | 0.8039 | 18 |
| mid_weak | 2.1054 | 2.0587 | -0.0467 | $76,563.68 | $74,594.60 | $-1,969.08 | -0.0045 | 0.7925 | 20 |
| old_thin | 0.5295 | 0.5113 | -0.0182 | $37,292.45 | $36,011.01 | $-1,281.44 | -0.0050 | 0.9167 | 31 |

Production impact: replay-only scout. A positive promotion must add shared `risk_engine` ATR-expansion state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.
