# exp-20260512-107 Signal-Day Positive Sector Tape Risk

Decision: `rejected_signal_day_positive_sector_tape_risk`.

Single variable: 1.10x cap-aware post-sizing risk top-up when the signal-day sector proxy open-to-close return is >= +1%. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.2340 | +0.0000 | $94,086.91 | $94,086.91 | $+0.00 | 0.8039 | 2 |
| mid_weak | 1.6689 | 1.6689 | +0.0000 | $61,813.40 | $61,813.40 | $+0.00 | 0.7925 | 0 |
| old_thin | 0.3853 | 0.3993 | +0.0140 | $28,544.11 | $29,364.37 | $+820.26 | 0.9167 | 4 |

Production impact: replay-only scout. Positive promotion would require shared `feature_layer`, `risk_engine`, and `portfolio_engine` code plus attribution key parity before live/default behavior changes.
