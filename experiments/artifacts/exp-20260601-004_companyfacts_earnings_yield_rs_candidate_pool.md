# exp-20260601-004: Companyfacts Earnings Yield + RS Candidate Pool

- decision: `rejected_companyfacts_earnings_yield_rs_candidate_pool`
- aggregate EV: `6.3596` -> `10.8628` (+4.5032)
- aggregate PnL: `$192,538.61` -> `$266,394.31` (+73,855.70)
- target trades: `154`
- max single positive share: `0.48095`
- positive PnL HHI: `0.398641`
- failed gates: `concentration_guard_passed`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 6.8404 | +2.7322 | $+26,710.45 | 86 |
| mid_weak | 2.1405 | 2.7782 | +0.6377 | $+11,787.88 | 19 |
| old_thin | 0.1109 | 1.2442 | +1.1333 | $+35,357.37 | 49 |

## Conclusion

The earnings-yield discriminator did not clear Gate 4, so no production or shared policy change is retained.

This scout used only filed-date Companyfacts quarterly EPS rows known on or before the signal date and signal-day OHLCV close from the accepted frozen Fundamental Growth + RS paper rows. It made no live/default order, ranking, sizing, exit, LLM, news, or watchlist change.

## Baseline Caveat

The current dirty-worktree replay baseline differs from the documented accepted core baseline in docs/backtesting.md. This prevents treating a positive replay as retained alpha without a clean parity baseline. The experiment is rejected anyway because the concentration guard failed.

- docs/backtesting.md accepted aggregate EV/PnL: `7.8941` / `$234,850.99`
- current dirty-worktree replay aggregate EV/PnL: `6.3596` / `$192,538.61`

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 23 | $44,549.06 | 0.48095 |
| MU | 79 | $29,202.73 | 0.402728 |
| GOOG | 14 | $2,796.41 | 0.063208 |
| RTX | 23 | $114.07 | 0.028167 |
| NFLX | 9 | $-100.04 | 0.016849 |
| NOW | 3 | $134.72 | 0.008097 |
| META | 3 | $-2,841.25 | 0.0 |
