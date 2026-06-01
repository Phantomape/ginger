# exp-20260601-012: Undercut-Reclaim Absorption Candidate Pool

- decision: `rejected_undercut_reclaim_absorption_candidate_pool`
- aggregate EV: `6.3596` -> `5.8855` (-0.4741)
- aggregate PnL delta: `$-5,869.16`
- target trades: `97`
- max single positive share: `0.167203`
- positive PnL HHI: `0.059503`
- Gate 1 docs-baseline match: `False`
- failed gates: `aggregate_ev_not_positive, aggregate_pnl_not_positive, window_ev_regression, window_pnl_regression, drawdown_drift_too_high, baseline_drift_blocks_promotion`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 3.6508 | -0.4574 | $-6,349.32 | 35 |
| mid_weak | 2.1405 | 2.0996 | -0.0409 | $-1,207.23 | 29 |
| old_thin | 0.1109 | 0.1351 | +0.0242 | $+1,687.39 | 33 |

## Conclusion

Gate 4 failed; no production or shared policy behavior is retained.

The rule uses same-day OHLCV known at the signal close, prior OHLCV context, SPY market-state context, and free SEC company-title metadata for operating-company hygiene. It is replay-only/default-off, so no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| HOOD | 2 | $1,684.12 | 0.167203 |
| DOW | 1 | $766.86 | 0.076136 |
| NCLH | 2 | $669.42 | 0.066462 |
| INSM | 1 | $570.64 | 0.056654 |
| TER | 1 | $503.97 | 0.050035 |
| GPN | 1 | $489.07 | 0.048556 |
| GNRC | 1 | $455.48 | 0.045221 |
| CNM | 1 | $383.95 | 0.038119 |
| PSKY | 1 | $330.00 | 0.032763 |
| HCA | 1 | $323.43 | 0.032111 |
