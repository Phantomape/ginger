# exp-20260601-010: Gap-Up Hold High-Close Candidate Pool

- decision: `rejected_gap_up_hold_high_close_candidate_pool`
- aggregate EV: `6.3596` -> `7.0943` (+0.7347)
- aggregate PnL delta: `$+3,391.06`
- target trades: `257`
- max single positive share: `0.163283`
- positive PnL HHI: `0.045217`
- Gate 1 docs-baseline match: `False`
- failed gates: `window_ev_regression, window_pnl_regression, drawdown_drift_too_high`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 4.2916 | +0.1834 | $+4,725.37 | 76 |
| mid_weak | 2.1405 | 2.7931 | +0.6526 | $+9,985.97 | 89 |
| old_thin | 0.1109 | 0.0096 | -0.1013 | $-11,320.28 | 92 |

## Conclusion

Gate 4 failed; no production or shared policy behavior is retained.

The rule uses only same-day OHLCV and prior 20-day OHLCV context known at the signal close. It is replay-only/default-off, so no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| AGQ | 5 | $7,567.07 | 0.163283 |
| ALAB | 3 | $2,530.53 | 0.054604 |
| SMR | 3 | $2,331.92 | 0.050318 |
| SOUN | 2 | $1,843.04 | 0.039769 |
| DJT | 4 | $1,820.50 | 0.039283 |
| ASTS | 2 | $1,645.27 | 0.035502 |
| MRVL | 3 | $1,635.78 | 0.035297 |
| AVGO | 2 | $1,477.74 | 0.031887 |
| HUT | 2 | $1,233.36 | 0.026614 |
| COIN | 2 | $1,134.06 | 0.024471 |
