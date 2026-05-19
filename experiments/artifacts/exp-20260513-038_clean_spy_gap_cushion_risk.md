# exp-20260513-038 Clean SPY-Leader Gap-Cushion Risk

Decision: `rejected_clean_spy_gap_cushion_risk`.

Single variable: cap-aware post-sizing risk top-up for already-clean SPY-relative leader signal-day winners whose existing stop has at least the already-surfaced 2% gap cushion. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.

## Sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|
| 1.025 | FAIL | -0.0002 | $+589.77 | old_thin | late_strong | 15 | +0.0010 |
| 1.050 | FAIL | -0.0006 | $+1,126.33 | old_thin | late_strong | 15 | +0.0020 |
| 1.075 | FAIL | -0.0057 | $+1,663.22 | old_thin | late_strong | 15 | +0.0030 |
| 1.100 | FAIL | -0.0100 | $+2,200.32 | old_thin | late_strong | 15 | +0.0040 |
| 1.150 | FAIL | -0.0206 | $+3,133.29 | old_thin | late_strong | 15 | +0.0061 |

Selected multiplier: `1.025`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.3739 | -0.0029 | $99,695.99 | $100,086.95 | $+390.96 | 0.8039 | 6 |
| mid_weak | 1.6788 | 1.6788 | +0.0000 | $62,644.67 | $62,644.67 | $+0.00 | 0.7925 | 2 |
| old_thin | 0.4292 | 0.4319 | +0.0027 | $31,563.29 | $31,762.10 | $+198.81 | 0.9167 | 7 |

Production impact: replay-only scout. Positive promotion requires shared `risk_engine` and `portfolio_engine` implementation plus attribution-key parity before live/default behavior changes.
