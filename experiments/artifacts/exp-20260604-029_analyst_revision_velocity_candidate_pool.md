# exp-20260604-029: Analyst Revision Velocity Candidate Pool

- decision: `rejected_analyst_revision_velocity_candidate_pool`
- aggregate EV: `7.8941` -> `8.1341` (+0.2400)
- aggregate PnL delta: `$+3,025.32`
- target trades: `43`
- max single positive share: `0.370072`
- positive PnL HHI: `0.211436`
- failed gates: `window_ev_regression, window_pnl_regression`
- numeric Gate 4 passed: `False`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3572 | +0.1944 | $+1,975.10 | 8 |
| mid_weak | 2.1402 | 2.1870 | +0.0468 | $+1,125.51 | 17 |
| old_thin | 0.5911 | 0.5899 | -0.0012 | $-75.29 | 18 |

## Conclusion

Gate 4 failed; no production or shared policy behavior is retained.

The tested fields are daily earnings-snapshot EPS estimates, same-day/prior OHLCV, and SPY relative strength. The result is replay-only/default-off: no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| MU | 5 | $2,178.21 | 0.370072 |
| TSLA | 4 | $1,227.92 | 0.20862 |
| DDOG | 2 | $647.12 | 0.109944 |
| LLY | 2 | $606.53 | 0.103048 |
| SPOT | 4 | $380.86 | 0.064707 |
| GE | 1 | $275.77 | 0.046853 |
| NFLX | 1 | $154.62 | 0.02627 |
| BKNG | 1 | $146.70 | 0.024924 |
| DIS | 2 | $91.57 | 0.015557 |
| JPM | 1 | $85.56 | 0.014536 |
