# exp-20260516-037 FINRA Short-Squeeze Demand Top-Up

Decision: `rejected_finra_short_squeeze_demand_topup`.

Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout stock signals with PIT-safe FINRA top-quartile days-to-cover plus RS20 leadership and signal-day green confirmation. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 1.0000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |
| 1.0125 | no | FAIL | +0.0000 | $+0.00 | - | - | 2 | mid_weak, old_thin | +0.0000 |
| 1.0250 | no | FAIL | +0.0000 | $+0.00 | - | - | 2 | mid_weak, old_thin | +0.0000 |
| 1.0500 | no | FAIL | +0.0000 | $+0.00 | - | - | 2 | mid_weak, old_thin | +0.0000 |
| 1.0750 | no | FAIL | +0.0000 | $+0.00 | - | - | 2 | mid_weak, old_thin | +0.0000 |
| 1.1000 | no | FAIL | +0.0000 | $+0.00 | - | - | 2 | mid_weak, old_thin | +0.0000 |

Selected non-control multiplier: `1.0125`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1344 | +0.0000 | $116,686.40 | $116,686.40 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 2.1054 | 2.1054 | +0.0000 | $76,563.68 | $76,563.68 | $+0.00 | +0.0000 | 0.7925 | 1 |
| old_thin | 0.5295 | 0.5295 | +0.0000 | $37,292.45 | $37,292.45 | $+0.00 | +0.0000 | 0.8667 | 1 |

Production impact: replay-only scout. A positive promotion must add a shared FINRA publication-lag adapter plus shared risk/sizing attribution used by both backtester.py and run.py, then rerun the canonical three-window backtest before live/default behavior changes.
