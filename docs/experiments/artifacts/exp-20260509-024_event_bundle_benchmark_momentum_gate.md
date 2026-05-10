# exp-20260509-024 Event Bundle Benchmark Momentum Gate

Decision: `rejected`

## Hypothesis

The frozen event overlay bundle may be higher quality when broad benchmark momentum is positive before entry; filtering event overlay trades by max(SPY, QQQ) 20-day return > 0 may remove weak-tape event losses without changing core A/B behavior.

## Three-Window Result

| Window | Core+Event EV | Gated EV | Delta EV | Core+Event PnL | Gated PnL | Delta PnL | Kept / blocked trades | Blocked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.5771 | 4.3421 | -0.2350 | $97,384.30 | $94,189.64 | $-3,194.66 | 6/3 | $+3,194.66 |
| mid_weak | 2.0830 | 2.0579 | -0.0251 | $67,850.50 | $67,472.35 | $-378.15 | 10/1 | $+378.15 |
| old_thin | 0.3938 | 0.3882 | -0.0056 | $28,745.97 | $28,543.07 | $-202.90 | 6/1 | $+202.90 |

## Aggregate

- Versus full event bundle EV: 7.0539 -> 6.7882 (-0.2657, -3.77%)
- Versus full event bundle PnL: $193,980.77 -> $190,205.06 (-3,775.71, -1.95%)
- Gated event bundle versus core EV delta: +0.7430
- Gated event bundle versus core PnL delta: $+12,528.13

## Decision Rationale

Rejected: the broad benchmark momentum participation gate did not improve the frozen full event bundle with enough three-window robustness and/or did not preserve the required positive edge versus core.

## Production Impact

Replay only. No live/default order path, core A/B behavior, event-source threshold, ranking, sizing, exits, or LLM/news behavior changed. A promoted version requires a shared run.py/backtester.py event policy and parity test.
