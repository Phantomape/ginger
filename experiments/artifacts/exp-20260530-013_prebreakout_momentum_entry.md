# exp-20260530-013 Pre-Breakout Momentum Entry

- Decision: `rejected_prebreakout_momentum_entry`
- Aggregate EV delta: `-1.9239`
- Aggregate PnL delta: `-48109.45`
- Gate 4 passed: `False`

| Window | EV before | EV after | EV delta | PnL delta | Max DD delta | Trades delta | Signals survived delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 5.1628 | 4.6483 | -0.5145 | $-5,600.71 | 0.0005 | 10.0 | 19.0 |
| mid_weak | 2.1402 | 0.7969 | -1.3433 | $-40,339.83 | -0.0565 | 7.0 | 15.0 |
| old_thin | 0.5911 | 0.5250 | -0.0661 | $-2,168.91 | -0.0113 | 9.0 | 18.0 |

This runner is replay-only. It temporarily injects the entry source inside signal generation and does not alter production code.
