# exp-20260517-011 Overstacked Generic Boost Haircut

Decision: `rejected_overstacked_generic_boost_haircut`.

Single variable: post-sizing risk multiplier for already-qualified trend/breakout stock signals that received both generic risk-on and SPY-relative leader boosts while lacking own-green and RS20 confirmation. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|
| 0.250 | no | FAIL | +0.0841 | $+2,268.81 | old_thin | - | 2 | old_thin | +0.0000 |
| 0.500 | no | FAIL | +0.0554 | $+1,514.82 | old_thin | - | 2 | old_thin | +0.0000 |
| 0.750 | no | FAIL | +0.0275 | $+759.64 | old_thin | - | 2 | old_thin | +0.0000 |
| 0.900 | no | FAIL | +0.0124 | $+306.53 | old_thin | - | 2 | old_thin | +0.0000 |
| 1.000 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | - | +0.0000 |

Selected non-control multiplier: `0.25`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $78,110.11 | $78,110.11 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.5911 | 0.6752 | +0.0841 | $39,667.96 | $41,936.77 | $+2,268.81 | -0.0289 | 0.9167 | 2 |

Production impact: replay-only scout. A positive promotion must add a shared state and sizing key in `risk_engine.py` / `portfolio_engine.py`, then rerun the canonical three-window backtest before live/default behavior changes.
