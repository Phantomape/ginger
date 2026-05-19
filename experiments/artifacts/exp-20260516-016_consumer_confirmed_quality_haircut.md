# exp-20260516-016 Consumer Confirmed-Quality Haircut

Decision: `rejected_consumer_confirmed_quality_haircut`.

Single variable: cap-aware post-sizing haircut for existing Consumer Discretionary `trend_long` / `breakout_long` signals that already have `core_confirmed_quality_state=true`. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Windows | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---|---:|
| 0.95 | FAIL | +0.0021 | $+145.23 | old_thin | - | 2 | mid_weak, old_thin | +0.0000 |
| 0.90 | FAIL | +0.0077 | $+281.43 | old_thin | - | 2 | mid_weak, old_thin | +0.0000 |
| 0.85 | FAIL | +0.0099 | $+426.65 | old_thin | - | 2 | mid_weak, old_thin | +0.0000 |
| 0.75 | FAIL | +0.0178 | $+714.95 | old_thin | - | 2 | mid_weak, old_thin | +0.0000 |

Selected multiplier: `0.75`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1344 | +0.0000 | $116,686.40 | $116,686.40 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 2.1016 | 2.1016 | +0.0000 | $76,421.93 | $76,421.93 | $+0.00 | +0.0000 | 0.7925 | 1 |
| old_thin | 0.5294 | 0.5472 | +0.0178 | $37,282.59 | $37,997.54 | $+714.95 | -0.0048 | 0.9167 | 1 |

Production impact: replay-only scout. A positive promotion must move the same state and sizing helper into shared `risk_engine.py` / `portfolio_engine.py`, add attribution-key parity, and rerun the canonical three-window backtest before any production behavior changes.
