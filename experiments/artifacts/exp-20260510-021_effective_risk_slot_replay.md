# exp-20260510-021 Effective Risk-Slot Replay

## Decision

- decision: rejected
- gate4_passed: False
- aggregate EV delta: -2.9205
- aggregate PnL delta: -61666.22
- windows EV improved: 0
- windows EV regressed: 3

## Three-Window Metrics

| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Base DD | After DD | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 2.1706 | -2.0634 | 94086.91 | 73833.86 | -20253.05 | 0.0548 | 0.0456 | 17 | 0.9474 |
| mid_weak | 1.6689 | 1.1769 | -0.4920 | 61813.40 | 44746.53 | -17066.87 | 0.0941 | 0.0423 | 12 | 0.8235 |
| old_thin | 0.3853 | 0.0202 | -0.3651 | 28544.11 | 4197.81 | -24346.30 | 0.0815 | 0.0663 | 19 | 0.9500 |

## Production Impact

- Replay-only runtime patch; production files are unchanged.
- A positive result still requires shared `production_parity.py` / `run.py` / `backtester.py` implementation and parity tests before live/default use.

## Interpretation

The alpha question was worth testing because nominal slots over-penalize haircut positions and under-penalize boosted risk leaders. The replay does not justify replacing the accepted nominal slot policy on the current frozen windows.
