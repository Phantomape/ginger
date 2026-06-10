# exp-20260610-025: Revision Acceleration Residual Leadership Candidate Pool

- decision: `rejected_revision_acceleration_residual_leadership_candidate_pool`
- aggregate EV: `7.8941` -> `7.8454` (-0.0487)
- aggregate PnL delta: `$-1,186.35`
- target trades: `16`
- max single positive share: `0.305199`
- positive PnL HHI: `0.231836`
- failed gates: `aggregate_ev_not_positive, aggregate_pnl_not_positive, window_ev_regression, window_pnl_regression, target_sample_too_small, drawdown_drift_too_high, accepted_revision_adapter_not_beaten`
- numeric Gate 4 passed: `False`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1623 | -0.0005 | $-9.99 | 1 |
| mid_weak | 2.1402 | 2.1172 | -0.0230 | $-268.84 | 9 |
| old_thin | 0.5911 | 0.5659 | -0.0252 | $-907.52 | 6 |

## Conclusion

Gate 4 failed versus the core baseline; revision acceleration plus residual leadership did not produce a robust retained alpha.

The tested fields are daily earnings-snapshot EPS estimates, same-day/prior OHLCV, and SPY relative strength. The result is replay-only/default-off: no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| NFLX | 1 | $154.62 | 0.305199 |
| MU | 1 | $135.40 | 0.267261 |
| DIS | 2 | $91.57 | 0.180747 |
| JPM | 1 | $85.56 | 0.168884 |
| AAPL | 2 | $39.47 | 0.077908 |
| PLTR | 2 | $-1,181.66 | None |
| AMD | 1 | $-300.21 | None |
| CRDO | 3 | $-102.02 | None |
| AVGO | 2 | $-95.75 | None |
| GS | 1 | $-13.33 | None |
