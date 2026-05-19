# exp-20260512-024 Pullback/Reclaim Entry

- Decision: `rejected_pullback_reclaim_entry`
- Aggregate EV delta: `-2.3009`
- Aggregate PnL delta: `-48599.83`

| Window | EV before | EV after | EV delta | PnL delta | Max DD delta | Trades delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.2340 | 3.2913 | -0.9427 | $-2,402.40 | 0.0148 | 12.0 |
| mid_weak | 1.6689 | 0.6409 | -1.0280 | $-26,403.78 | -0.0044 | 16.0 |
| old_thin | 0.3853 | 0.0551 | -0.3302 | $-19,793.65 | 0.0333 | 8.0 |

The tested pullback/reclaim entry shape added many candidates but degraded EV in every canonical window, so no shared production policy was promoted.
