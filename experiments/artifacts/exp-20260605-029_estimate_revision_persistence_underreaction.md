# exp-20260605-029: Estimate Revision Persistence Underreaction

- decision: `rejected_estimate_revision_persistence_underreaction`
- aggregate EV: `7.8941` -> `7.5916` (-0.3025)
- aggregate PnL delta: `$-2,693.67`
- target trades: `43`
- max single positive share: `0.351213`
- positive PnL HHI: `0.201626`
- failed gates: `aggregate_ev_not_positive, aggregate_pnl_not_positive, window_ev_regression, window_pnl_regression`
- numeric Gate 4 passed: `False`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.8199 | -0.3429 | $-3,662.59 | 16 |
| mid_weak | 2.1402 | 2.1696 | +0.0294 | $+498.25 | 20 |
| old_thin | 0.5911 | 0.6021 | +0.0110 | $+470.67 | 7 |

## Conclusion

Gate 4 failed; no production or shared policy behavior is retained.

The tested fields are daily earnings-snapshot EPS estimates, same-day/prior OHLCV, and SPY relative strength. The result is replay-only/default-off: no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| NFLX | 2 | $+391.94 | 0.351213 |
| AVGO | 2 | $+169.65 | 0.152022 |
| MCD | 3 | $+154.14 | 0.138123 |
| GS | 3 | $+152.84 | 0.136958 |
| GE | 1 | $+110.28 | 0.098821 |
| MSFT | 1 | $+71.70 | 0.06425 |
| MA | 2 | $+65.41 | 0.058613 |
| AMD | 2 | $-1,011.86 | None |
| NVDA | 6 | $-770.32 | None |
| CRDO | 1 | $-597.26 | None |
