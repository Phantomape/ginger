# exp-20260601-011: Stock-Only Gap-Up Hold High-Close Candidate Pool

- decision: `rejected_stock_only_gap_hold_high_close_candidate_pool`
- aggregate EV: `6.3596` -> `6.5728` (+0.2132)
- aggregate PnL delta: `$-2,020.10`
- target trades: `247`
- max single positive share: `0.067595`
- positive PnL HHI: `0.027521`
- Gate 1 docs-baseline match: `False`
- failed gates: `aggregate_pnl_not_positive, window_ev_regression, window_pnl_regression, drawdown_drift_too_high`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 3.7390 | -0.3692 | $-2,837.33 | 71 |
| mid_weak | 2.1405 | 2.8153 | +0.6748 | $+10,411.11 | 87 |
| old_thin | 0.1109 | 0.0185 | -0.0924 | $-9,593.88 | 89 |

## Conclusion

Gate 4 failed; no production or shared policy behavior is retained.

The rule uses only same-day OHLCV and prior 20-day OHLCV context known at the signal close plus free SEC company-title metadata for stock-only governance. It is replay-only/default-off, so no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| ALAB | 3 | $2,530.53 | 0.067595 |
| SMR | 3 | $2,331.92 | 0.06229 |
| SOUN | 2 | $1,843.04 | 0.049231 |
| DJT | 4 | $1,820.50 | 0.048629 |
| ASTS | 2 | $1,645.27 | 0.043948 |
| MRVL | 3 | $1,635.78 | 0.043695 |
| AVGO | 2 | $1,477.74 | 0.039473 |
| HUT | 2 | $1,233.36 | 0.032945 |
| COIN | 2 | $1,134.06 | 0.030293 |
| IREN | 2 | $1,090.90 | 0.02914 |
