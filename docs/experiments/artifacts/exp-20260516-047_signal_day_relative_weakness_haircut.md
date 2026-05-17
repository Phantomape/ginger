# exp-20260516-047 Signal-Day Relative Weakness Haircut

Decision: `rejected_signal_day_relative_weakness_haircut`.

Single variable: post-sizing risk multiplier for already-qualified trend/breakout stock signals whose signal day is both not an own green candle and not SPY-outperformance. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 0.5000 | no | FAIL | -0.7001 | $-16,941.28 | - | late_strong, mid_weak, old_thin | 13 | late_strong, mid_weak, old_thin | +0.0003 |
| 0.6500 | no | FAIL | -0.4674 | $-11,345.10 | - | late_strong, mid_weak, old_thin | 13 | late_strong, mid_weak, old_thin | +0.0003 |
| 0.7500 | no | FAIL | -0.3367 | $-8,037.84 | old_thin | late_strong, mid_weak | 13 | late_strong, mid_weak, old_thin | +0.0001 |
| 0.8500 | no | FAIL | -0.1990 | $-4,620.32 | old_thin | late_strong, mid_weak | 13 | late_strong, mid_weak, old_thin | +0.0003 |
| 0.9000 | no | FAIL | -0.1302 | $-3,085.51 | old_thin | late_strong, mid_weak | 13 | late_strong, mid_weak, old_thin | +0.0001 |
| 0.9500 | no | FAIL | -0.0596 | $-1,582.55 | old_thin | late_strong, mid_weak | 13 | late_strong, mid_weak, old_thin | +0.0000 |
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |

Selected non-control multiplier: `0.95`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1361 | 5.1163 | -0.0198 | $116,727.26 | $116,283.10 | $-444.16 | +0.0000 | 0.8039 | 4 |
| mid_weak | 2.1084 | 2.0682 | -0.0402 | $76,665.80 | $75,761.02 | $-904.78 | +0.0000 | 0.7925 | 5 |
| old_thin | 0.5903 | 0.5907 | +0.0004 | $39,615.16 | $39,381.55 | $-233.61 | -0.0020 | 0.9000 | 4 |

Production impact: replay-only scout. A positive promotion must add a shared `risk_engine` relative-weakness state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.
