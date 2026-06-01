# exp-20260601-019: Companyfacts FCF Yield + RS Candidate Pool

- decision: `rejected_companyfacts_fcf_yield_rs_candidate_pool`
- aggregate EV: `6.3596` -> `9.1473` (+2.7877)
- aggregate PnL: `$192,538.61` -> `$243,457.43` (+50,918.82)
- target trades: `44`
- max single positive share: `0.555301`
- positive PnL HHI: `0.4314`
- alpha failed gates: `concentration_guard_passed`
- retention failed gates: `concentration_guard_passed, baseline_matches_docs_for_retention`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 5.8999 | +1.7917 | $+18,747.63 | 14 |
| mid_weak | 2.1405 | 2.1954 | +0.0549 | $+850.72 | 2 |
| old_thin | 0.1109 | 1.0520 | +0.9411 | $+31,320.47 | 28 |

## Conclusion

The FCF-yield discriminator did not clear Gate 4 alpha checks, so no production or shared policy change is retained.

This scout used only filed-date Companyfacts operating cash flow, capex, and diluted-share rows known on or before the signal date, plus the signal-day close from the accepted frozen Fundamental Growth + RS paper rows. It made no live/default order, ranking, sizing, exit, LLM, news, or watchlist change.

## Baseline Caveat

The current dirty-worktree replay baseline differs from the documented accepted core baseline in docs/backtesting.md. A positive replay lead cannot be retained or promoted until a clean baseline/parity decision explains or accepts the drift.

- docs/backtesting.md accepted aggregate EV/PnL: `7.8941` / `$234,850.99`
- current replay aggregate EV/PnL: `6.3596` / `$192,538.61`

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 16 | $30,027.56 | 0.555301 |
| MU | 14 | $18,747.63 | 0.344547 |
| COIN | 1 | $3,129.12 | 0.057507 |
| NFLX | 9 | $-100.04 | 0.028803 |
| NOW | 3 | $134.72 | 0.013842 |
| META | 1 | $-1,020.17 | 0.0 |
