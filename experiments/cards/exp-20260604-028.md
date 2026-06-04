# exp-20260604-028: Nasdaq Reg SHO + FINRA Candidate Pool

- decision: `rejected_nasdaq_regsho_finra_candidate_pool`
- aggregate EV: `7.8941` -> `7.8941` (+0.0000)
- aggregate PnL delta: `$+0.00`
- target trades: `0`
- max single positive share: `None`
- positive PnL HHI: `None`
- failed gates: `aggregate_ev_not_positive, aggregate_pnl_not_positive, window_ev_regression, target_sample_too_small, target_window_coverage_too_small, target_concentration_failed`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $+0.00 | 0 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $+0.00 | 0 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $+0.00 | 0 |

## Conclusion

Gate 4 failed; no production or shared policy behavior is retained.

The tested fields are official NasdaqTrader Reg SHO threshold files used only for next-open paper entry, official FINRA rows after publication-date rules, and same-day/prior OHLCV. The result is replay-only/default-off: no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
