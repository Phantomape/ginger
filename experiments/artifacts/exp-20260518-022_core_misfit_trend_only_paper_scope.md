# exp-20260518-022 Core Misfit Trend-Only Paper Scope

Decision: `accepted_default_off_core_misfit_trend_only_paper_scope`.

Single variable: default-off CORE_MISFIT_PAPER `target_strategies` changes from `trend_long + breakout_long` to `trend_long` only.

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Paper trades | 9 | 7 | -2 |
| Paper PnL | $6,079.66 | $5,799.05 | $-280.61 |
| PnL retention | 100.00% | 95.38% | n/a |
| Win rate | 66.67% | 71.43% | 4.76% |
| Positive windows | 1 | 2 | 1 |
| Worst trade | -4.53% | -2.03% | 2.50% |
| Max DD | 0.73% | 0.20% | -0.54% |

| Window | Before trades | Before PnL | After trades | After PnL |
|---|---:|---:|---:|---:|
| late_strong | 0 | $0.00 | 0 | $0.00 |
| mid_weak | 2 | $-776.16 | 1 | $8.81 |
| old_thin | 7 | $6,855.82 | 6 | $5,790.24 |

Core live metrics are intentionally unchanged; this only narrows a default-off paper ledger.
Gate 4 passed: `True`.
