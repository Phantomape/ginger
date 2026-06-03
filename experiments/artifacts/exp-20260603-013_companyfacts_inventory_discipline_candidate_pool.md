# exp-20260603-013: Companyfacts Inventory Discipline Candidate Pool

- decision: `rejected_companyfacts_inventory_discipline_candidate_pool`
- aggregate EV: `7.8941` -> `11.3301` (+3.4360)
- aggregate PnL: `$234,850.99` -> `$273,671.26` (+38,820.27)
- target trades: `130`
- max single positive share: `0.660334`
- positive PnL HHI: `0.511525`
- failed gates: `all_windows_expected_value_improved, all_windows_pnl_improved, concentration_guard_passed`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.2315 | +2.0687 | $+21,192.89 | 64 |
| mid_weak | 2.1402 | 3.6439 | +1.5037 | $+23,107.68 | 38 |
| old_thin | 0.5911 | 0.4547 | -0.1364 | $-5,480.30 | 28 |

## Conclusion

Gate 4 alpha checks failed; no strategy or production behavior is retained.

This scout used only SEC Companyfacts rows filed on or before the signal date. It made no live/default order, shared ranking, sizing, exit, LLM, news, or watchlist change.

## Baseline Caveat

Current replay aggregate baseline matches docs/backtesting.md within tolerance.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| MU | 79 | $29,202.73 | 0.660334 |
| CRDO | 21 | $12,233.07 | 0.267126 |
| AVGO | 16 | $-2,567.60 | 0.063627 |
| RTX | 14 | $-47.93 | 0.008913 |
