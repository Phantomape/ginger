# exp-20260519-019 Core Misfit Residual Ticker Paper Scope

Decision: `rejected_core_misfit_residual_ticker_paper_scope`.

Single causal variable: expand the default-off CORE_MISFIT_PAPER ticker scope beyond `TSM/ISRG/V/DDOG` for `trend_long` paper observation.

Residual candidates: `9`.
Residual inverse 10d PnL: `$-1,121.37`.
Residual long 10d PnL: `$-408.71`.
Gate 4 passed: `False`.

| Window | Candidates | Long PnL | Inverse 10d PnL |
|---|---:|---:|---:|
| late_strong | 1 | $-90.88 | $84.11 |
| mid_weak | 3 | $-348.75 | $275.10 |
| old_thin | 5 | $30.92 | $-1,480.58 |

| Ticker | Candidates | Windows | Long PnL | Inverse 10d PnL | Sample pass |
|---|---:|---|---:|---:|---|
| MCD | 1 | old_thin | $-1,411.27 | $493.32 | no |
| SNOW | 1 | mid_weak | $-353.83 | $289.04 | no |
| META | 3 | late_strong, mid_weak, old_thin | $-27.50 | $6.88 | no |
| PLTR | 3 | mid_weak, old_thin | $105.47 | $-115.19 | no |
| TRIP | 1 | old_thin | $1,278.42 | $-1,795.42 | no |

Core live metrics are unchanged; no policy was promoted.
