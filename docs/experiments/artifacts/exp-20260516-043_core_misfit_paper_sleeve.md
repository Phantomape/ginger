# exp-20260516-043 Core Misfit Paper Sleeve

Decision: `accepted_default_off_core_misfit_paper_sleeve`.

Core replay metrics are intentionally unchanged. This experiment only copies real core misfit entries and entry-loop candidates into paper-only no-trade, fast-long, and inverse-short attribution surfaces.

| Ticker | Trades | Core PnL | No-trade value | Inverse actual-exit PnL | Windows |
|---|---:|---:|---:|---:|---|
| DDOG | 2 | $-2,187.09 | $2,187.09 | $1,675.00 | old_thin |
| ISRG | 2 | $-464.28 | $464.28 | $177.03 | mid_weak, old_thin |
| TSM | 3 | $-133.35 | $133.35 | $109.07 | mid_weak, old_thin |
| V | 2 | $-3,684.85 | $3,684.85 | $2,424.19 | old_thin |

| Horizon | Actual fast-long PnL | Actual inverse-short PnL | Candidate fast-long PnL | Candidate inverse-short PnL |
|---|---:|---:|---:|---:|
| 1d | $-2,881.19 | $866.43 | $-2,883.68 | $866.47 |
| 3d | $-5,698.33 | $3,687.80 | $-5,700.83 | $3,687.84 |
| 5d | $-6,480.12 | $4,470.76 | $-6,482.61 | $4,470.79 |
| 10d | $-8,086.55 | $6,079.62 | $-8,089.03 | $6,079.66 |

Primary candidate events: 9 total, 9 fillable, 9 entered, 0 slot-sliced.

Production impact: replay-only/default-off paper tracking. No live shorting, no core exclusion, no entry/exit/ranking/sizing change.
