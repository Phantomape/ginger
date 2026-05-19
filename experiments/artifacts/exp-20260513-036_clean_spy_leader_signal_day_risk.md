# exp-20260513-036 Clean SPY-Leader Signal-Day Risk

Decision: `accepted_clean_spy_leader_signal_day_1_10_risk_topup`.

Single variable: cap-aware post-sizing share multiplier for signals that already qualify for the clean risk-on SPY-relative leader path and also beat SPY open-to-close on the signal day.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3663 | 4.3768 | +0.0105 | $98,115.26 | $99,695.99 | $+1,580.73 | +0.0034 | 0.8039 |
| mid_weak | 1.6788 | 1.6788 | +0.0000 | $62,644.67 | $62,644.67 | $+0.00 | +0.0000 | 0.7925 |
| old_thin | 0.4151 | 0.4292 | +0.0141 | $30,524.01 | $31,563.29 | $+1,039.28 | +0.0015 | 0.9167 |

## Sweep

| Multiplier | Gate 4 | Aggregate dEV | Aggregate dPnL | Max DD worse | Adjusted signals |
|---:|---|---:|---:|---:|---:|
| 1.050 | PASS | +0.0092 | $+1,273.15 | +0.0013 | 19 |
| 1.075 | FAIL | +0.0107 | $+1,930.45 | +0.0024 | 19 |
| 1.100 | PASS | +0.0246 | $+2,620.01 | +0.0034 | 19 |
| 1.150 | FAIL | +0.0306 | $+3,682.20 | +0.0051 | 19 |

Production impact: accepted implementation lives in shared `risk_engine.py` and `portfolio_engine.py`; `backtester.py` only adds the attribution key. The daily production path already calls the shared modules.
