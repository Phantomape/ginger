# exp-20260601-030: Companyfacts Cost-Liquidity Support

- decision: `accepted_shared_companyfacts_cost_liquidity_support`
- aggregate EV: `13.0745` -> `13.4753` (+0.4008)
- aggregate PnL: `$305,514.70` -> `$311,052.25` (+5,537.55)
- incremental target trades: `252`
- max single positive share: `0.427643`
- positive PnL HHI: `0.252329`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.8610 | 5.9847 | +0.1237 | $+1,284.70 | 68 |
| mid_weak | 5.5629 | 5.7289 | +0.1660 | $+2,026.98 | 86 |
| old_thin | 1.6506 | 1.7617 | +0.1111 | $+2,225.87 | 98 |

## Production Parity

This replay uses only signal-day OHLCV and existing Companyfacts target rows known after signal-date close and before next-open paper entry. No live/default orders, core ranking, core sizing, exits, LLM, or news path changed.

## Conclusion

Companyfacts cost-liquidity support passed the three-window alpha gate and is retained in the shared default-off paper adapter with no live order impact.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 70 | $2,751.36 | 0.427643 |
| PLTR | 48 | $1,141.05 | 0.180796 |
| MU | 43 | $956.67 | 0.139886 |
| AMD | 15 | $722.36 | 0.103238 |
| CRDO | 28 | $151.35 | 0.062144 |
| GOOG | 14 | $146.80 | 0.042742 |
| AVGO | 16 | $-134.80 | 0.026241 |
| NFLX | 9 | $-5.26 | 0.011393 |
| NOW | 3 | $7.07 | 0.005475 |
| NVDA | 1 | $3.19 | 0.000442 |
