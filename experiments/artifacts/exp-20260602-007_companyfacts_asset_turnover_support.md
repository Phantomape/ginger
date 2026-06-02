# exp-20260602-007: Companyfacts Asset-Turnover Support

- decision: `rejected_companyfacts_asset_turnover_support`
- aggregate EV: `15.7099` -> `15.9615` (+0.2516)
- aggregate PnL: `$353,364.63` -> `$357,425.17` (+4,060.54)
- incremental target trades: `188`
- max single positive share: `0.576923`
- positive PnL HHI: `0.393035`
- failed gates: `concentration_guard_passed`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 7.2164 | 7.2615 | +0.0451 | $+606.59 | 66 |
| mid_weak | 5.7284 | 5.7828 | +0.0544 | $+922.05 | 55 |
| old_thin | 2.7651 | 2.9172 | +0.1521 | $+2,531.90 | 67 |

## Production Parity

This replay uses SEC Companyfacts rows with filed dates on or before the signal date. It does not change shared production/backtest policy, live orders, core ranking, sizing, exits, LLM, or news behavior. Any future promotion requires a shared default-off adapter and parity tests.

## Conclusion

Asset-turnover support failed Gate 4; no shared strategy or production behavior is retained.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 73 | $2,891.86 | 0.576923 |
| MU | 43 | $1,004.50 | 0.188065 |
| PLTR | 21 | $701.23 | 0.145455 |
| GOOG | 14 | $154.16 | 0.057467 |
| NFLX | 9 | $-5.50 | 0.015319 |
| CRDO | 21 | $-539.84 | 0.008814 |
| NOW | 3 | $7.42 | 0.007362 |
| NVDA | 1 | $3.35 | 0.000594 |
| META | 3 | $-156.63 | 0.0 |
