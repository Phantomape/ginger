# exp-20260515-046 exec_lag_rr_spy_confirmed_risk

Decision: `rejected_exec_lag_rr_spy_confirmed_risk`.

Single variable: cap-aware post-sizing top-up for `trend_long` / `breakout_long` non-ETF/non-commodity stock signals in the same-day top quartile of `exec_lag_adj_net_rr` that also outperformed SPY open-to-close on the signal day. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, and slots were unchanged.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.0125 | FAIL | +0.0043 | $+303.46 | late_strong | mid_weak, old_thin | 12 | +0.0008 |
| 1.0250 | FAIL | +0.0104 | $+776.33 | late_strong, mid_weak | old_thin | 15 | +0.0020 |
| 1.0500 | FAIL | -0.0035 | $+1,521.36 | late_strong | mid_weak, old_thin | 20 | +0.0036 |
| 1.0750 | FAIL | +0.0103 | $+2,411.42 | late_strong, mid_weak | old_thin | 20 | +0.0056 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 5.1141 | +0.0077 | $116,319.10 | $116,759.41 | $+440.31 | +0.0010 | 0.8039 | 5 |
| mid_weak | 2.0987 | 2.1024 | +0.0037 | $76,035.04 | $76,448.30 | $+413.26 | +0.0020 | 0.7925 | 4 |
| old_thin | 0.5294 | 0.5284 | -0.0010 | $37,282.59 | $37,205.35 | $-77.24 | +0.0008 | 0.8667 | 6 |

Production impact: replay-only scout. A positive promotion must move the state and sizing helper into shared `risk_engine.py` / `portfolio_engine.py`, add attribution keys, update parity docs, and add focused tests before production behavior changes.
