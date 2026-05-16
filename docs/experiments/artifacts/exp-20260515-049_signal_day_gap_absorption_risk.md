# exp-20260515-049 signal_day_gap_absorption_risk

Decision: `rejected_signal_day_gap_absorption_risk`.

Single variable: cap-aware post-sizing top-up for existing `trend_long` / `breakout_long` non-ETF/non-commodity stock signals in the top quartile of production-visible signal-day gap-absorption strength. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | +0.0000 | $+0.00 | - | - | 1 | +0.0000 |
| 1.0250 | FAIL | +0.0000 | $+0.00 | - | - | 1 | +0.0000 |
| 1.0500 | FAIL | +0.0000 | $+0.00 | - | - | 1 | +0.0000 |
| 1.0750 | FAIL | +0.0000 | $+0.00 | - | - | 1 | +0.0000 |

Selected multiplier: `1.0125`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1064 | +0.0000 | $116,319.10 | $116,319.10 | $+0.00 | +0.0000 | 0.8039 | 0 |
| mid_weak | 2.0987 | 2.0987 | +0.0000 | $76,035.04 | $76,035.04 | $+0.00 | +0.0000 | 0.7925 | 0 |
| old_thin | 0.5294 | 0.5294 | +0.0000 | $37,282.59 | $37,282.59 | $+0.00 | +0.0000 | 0.8667 | 1 |

Production impact: replay-only scout. A positive promotion must move the state and sizing helper into shared `feature_layer.py` / `risk_engine.py` / `portfolio_engine.py`, add attribution keys, update parity docs, and add focused tests before production behavior changes.
