# exp-20260513-109 Clean SPY-Leader Non-Confirmation Risk

Decision: `rejected_clean_spy_leader_nonconfirmation_risk`.

Single variable: post-sizing risk multiplier for clean risk-on SPY-relative leaders whose signal-day ticker open-to-close return did not beat SPY.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.2977 | -0.0791 | $99,695.99 | $98,117.40 | $-1,578.59 | +0.0003 | 0.8039 | 7 |
| mid_weak | 1.6788 | 1.6790 | +0.0002 | $62,644.67 | $62,653.87 | $+9.20 | +0.0000 | 0.7925 | 4 |
| old_thin | 0.4292 | 0.4296 | +0.0004 | $31,563.29 | $31,125.78 | $-437.51 | -0.0042 | 0.9167 | 5 |

## Sweep

| Multiplier | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |
|---:|---|---:|---:|---:|---:|
| 0.50 | FAIL | -0.4728 | $-11,400.20 | +0.0015 | 16 |
| 0.75 | FAIL | -0.2078 | $-5,280.94 | +0.0006 | 16 |
| 0.90 | FAIL | -0.0785 | $-2,006.90 | +0.0003 | 16 |

Production impact: no shared strategy code is promoted unless Gate 4 passes. A positive promotion would need the rule in shared `portfolio_engine.py`, with production continuing to call the same shared sizing path.
