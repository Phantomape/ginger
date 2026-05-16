# exp-20260516-035 FINRA Short-Crowding Risk Haircut

Decision: `rejected_finra_short_crowding_risk_haircut`.

Single variable: post-sizing risk multiplier for already-qualified trend/breakout stock signals whose latest PIT-safe FINRA days-to-cover value is in the same-day universe top quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 0.25 | no | FAIL | -0.5954 | $-16,172.26 | mid_weak | late_strong, old_thin | 17 | late_strong, mid_weak, old_thin | +0.0000 |
| 0.50 | no | FAIL | -0.3159 | $-9,337.07 | mid_weak | late_strong, old_thin | 17 | late_strong, mid_weak, old_thin | +0.0002 |
| 0.75 | no | FAIL | -0.1612 | $-4,579.29 | mid_weak | late_strong, old_thin | 17 | late_strong, mid_weak, old_thin | +0.0004 |
| 1.00 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |

Selected non-control multiplier: `0.75`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 4.9926 | -0.1418 | $116,686.40 | $114,506.92 | $-2,179.48 | +0.0004 | 0.8039 | 3 |
| mid_weak | 2.1054 | 2.1065 | +0.0011 | $76,563.68 | $76,597.00 | $+33.32 | +0.0000 | 0.7925 | 4 |
| old_thin | 0.5295 | 0.5090 | -0.0205 | $37,292.45 | $34,859.32 | $-2,433.13 | -0.0075 | 0.8667 | 10 |

Production impact: replay-only scout. A positive promotion must add a shared FINRA publication-lag adapter plus shared risk/sizing attribution used by both backtester.py and run.py, then rerun the canonical three-window backtest before live/default behavior changes.
