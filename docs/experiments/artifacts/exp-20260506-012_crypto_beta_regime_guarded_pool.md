# exp-20260506-012 crypto-beta regime-guarded pool

Decision: `rejected`
Best variant: `btc_etfs_guarded`

| window | baseline EV | after EV | EV delta | PnL delta | added trades | guard passed/seen |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 3.3342 | -0.0849 | $-1,241.65 | 0 | 0/0 |
| mid_weak | 1.4415 | 1.4415 | +0.0000 | $0.00 | 0 | 3/3 |
| old_thin | 0.3624 | 0.3624 | +0.0000 | $0.00 | 0 | 3/3 |

Aggregate:
- EV delta sum: `-0.0849`
- PnL delta sum: `$-1,241.65`
- Added trade PnL: `$0.00`
- Gate 4: `False`

Production impact: replay-only. A positive future promotion must share the BTC-tape guard between backtest and run.py.
