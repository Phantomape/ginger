# exp-20260515-022 RS60 Unextended Leadership Risk

Decision: `rejected_rs60_unextended_leadership_risk`.

Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout non-ETF/non-commodity stocks with `rs60_top_quintile_state=true` and `price_vs_200ma_pct` below the same-day top-quartile extension cutoff.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0334 | 5.0334 | +0.0000 | $115,183.05 | $115,183.05 | $+0.00 | 0.0668 | 0.8039 | 0 |
| mid_weak | 2.0103 | 2.0103 | +0.0000 | $73,104.97 | $73,104.97 | $+0.00 | 0.1014 | 0.7925 | 1 |
| old_thin | 0.5099 | 0.5099 | +0.0000 | $35,657.24 | $35,657.24 | $+0.00 | 0.0934 | 0.9167 | 1 |

Production impact: replay-only scout. Positive promotion requires the helper in shared `portfolio_engine.py`, attribution keys in `backtester.py`, docs parity update, and focused parity tests before live/default behavior changes.
