# exp-20260515-041 Exec-Lag R:R Unreduced Leadership Risk

Decision: `rejected_exec_lag_rr_unreduced_leadership_risk`.

Single variable: cap-aware post-sizing top-up for `trend_long` / `breakout_long` non-ETF/non-commodity stock signals whose `exec_lag_adj_net_rr` is in the same-day top quartile and whose existing sizing did not already carry a risk-haircut multiplier below 1.0. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | -0.0243 | $-1,746.46 | mid_weak | old_thin | 6 | +0.0001 |
| 1.0250 | FAIL | -0.0243 | $-1,746.46 | mid_weak | old_thin | 6 | +0.0001 |
| 1.0500 | FAIL | -0.0243 | $-1,746.46 | mid_weak | old_thin | 6 | +0.0001 |
| 1.0750 | FAIL | -0.0243 | $-1,746.46 | mid_weak | old_thin | 6 | +0.0001 |

Selected multiplier: `1.0125`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1064 | +0.0000 | $116,319.10 | $116,319.10 | $+0.00 | +0.0000 | 0.8039 | 3 |
| mid_weak | 2.0987 | 2.0998 | +0.0011 | $76,035.04 | $76,079.75 | $+44.71 | +0.0000 | 0.7925 | 1 |
| old_thin | 0.5294 | 0.5040 | -0.0254 | $37,282.59 | $35,491.42 | $-1,791.17 | +0.0001 | 0.8667 | 2 |

Production impact: replay-only scout. A positive promotion must move the state and sizing helper into shared `risk_engine.py` / `portfolio_engine.py`, add attribution keys, update parity docs, and add focused tests before production behavior changes.
