# exp-20260606-016: Revision Surprise-History Confirmed Candidate Pool

- decision: `rejected_revision_surprise_history_confirmed_candidate_pool`
- aggregate EV: `7.8941` -> `8.0906` (+0.1965)
- aggregate PnL delta: `$+1,390.23`
- target trades: `39`
- max single positive share: `0.50927`
- positive PnL HHI: `0.310059`
- failed gates: `window_ev_regression, window_pnl_regression, drawdown_drift_too_high, target_concentration_failed`
- numeric Gate 4 passed: `False`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3568 | +0.1940 | $+1,965.11 | 9 |
| mid_weak | 2.1402 | 2.1870 | +0.0468 | $+1,125.50 | 17 |
| old_thin | 0.5911 | 0.5468 | -0.0443 | $-1,700.38 | 13 |

## Conclusion

Gate 4 failed; the surprise-history confirmation did not make revision velocity robust enough for retention.

The tested fields are daily earnings-snapshot EPS estimates, same-day/prior OHLCV, and SPY relative strength. The result is replay-only/default-off: no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| MU | 5 | $2,178.21 | 0.50927 |
| DDOG | 2 | $647.12 | 0.151298 |
| LLY | 2 | $606.53 | 0.141808 |
| GE | 1 | $275.76 | 0.064473 |
| NFLX | 1 | $154.62 | 0.03615 |
| BKNG | 1 | $146.70 | 0.034299 |
| DIS | 2 | $91.57 | 0.021409 |
| JPM | 1 | $85.56 | 0.020004 |
| MA | 2 | $46.21 | 0.010804 |
| AAPL | 2 | $39.47 | 0.009228 |
