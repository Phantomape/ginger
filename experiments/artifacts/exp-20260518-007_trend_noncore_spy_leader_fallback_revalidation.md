# exp-20260518-007 Trend Non-Core SPY-Leader Fallback Revalidation

Decision: `rejected_trend_noncore_spy_leader_fallback`.

Single variable: total risk multiplier for already-qualified `trend_long` SPY-relative leaders outside repeat-positive trend sectors. Breakouts, entries, ranking, exits, targets, candidate pool, LLM/news, and event sleeves were unchanged.

## Sweep

| Fallback total multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected trades | Affected windows | Max DD worse |
|---:|:---:|:---:|---:|---:|---|---|---:|---:|---:|
| 2.00 | yes | FAIL | +0.0000 | $+0.00 | - | - | 2 | 2 | +0.0000 |
| 1.50 | no | FAIL | +0.0284 | $-53.12 | late_strong | old_thin | 2 | 2 | +0.0004 |
| 1.25 | no | FAIL | +0.0569 | $+444.84 | late_strong | old_thin | 2 | 2 | +0.0004 |
| 1.00 | no | FAIL | +0.1134 | $+1,339.40 | late_strong | old_thin | 2 | 2 | +0.0003 |

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2915 | +0.1287 | $117,072.92 | $118,906.83 | $+1,833.91 | 0.8039 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $78,110.11 | $78,110.11 | $+0.00 | 0.7925 |
| old_thin | 0.5911 | 0.5758 | -0.0153 | $39,667.96 | $39,173.45 | $-494.51 | 0.8667 |

Production impact: replay-only scout. Passing evidence requires promotion through shared `portfolio_engine.py` and parity tests before changing live/default behavior.
