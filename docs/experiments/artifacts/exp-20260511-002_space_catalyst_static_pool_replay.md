# exp-20260511-002 Space Catalyst Static-Pool Replay

## Decision

- decision: rejected_static_pool_alpha
- gate4_passed: False
- aggregate EV delta: 2.3036
- aggregate PnL delta: 64577.73
- windows EV improved: 3
- windows EV regressed: 0
- added space trades: 25
- added space PnL: 79995.67

## Three-Window Metrics

| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Base DD | After DD | Trades | Survival | Space Trades | Space PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.3549 | 0.1209 | 94086.91 | 101752.53 | 7665.62 | 0.0548 | 0.0641 | 27 | 0.8261 | 9 | 11303.70 |
| mid_weak | 1.6689 | 3.6041 | 1.9352 | 61813.40 | 102390.22 | 40576.82 | 0.0941 | 0.0599 | 29 | 0.8537 | 9 | 45841.80 |
| old_thin | 0.3853 | 0.6328 | 0.2475 | 28544.11 | 44879.40 | 16335.29 | 0.0815 | 0.1171 | 28 | 0.9036 | 7 | 22850.17 |

## Included Tickers

RKLB, ASTS, LUNR, PL, RDW, BKSY, IRDM, VSAT, GSAT, SATS

## Interpretation

The pool is still useful as observe-only theme coverage, but the existing trend/breakout engine should not trade the space operating equities from static historical evidence. Forward observation or a separate event discriminator is required before revisiting live slots.

## Production Impact

- Static-pool replay only; no production order path, sizing path, or run adapter changed.
- A positive result would still require a separate default-off forward queue/pilot promotion with parity tests.
