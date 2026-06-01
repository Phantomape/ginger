# exp-20260601-031: Companyfacts Dual-Growth Pair Support

- decision: `positive_replay_lead_not_promoted_requires_forward_rows`
- aggregate EV: `13.4753` -> `13.8751` (+0.3998)
- aggregate PnL: `$311,052.25` -> `$316,707.91` (+5,655.66)
- incremental target trades: `231`
- max single positive share: `0.456608`
- positive PnL HHI: `0.282941`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.9847 | 6.1388 | +0.1541 | $+1,636.92 | 66 |
| mid_weak | 5.7289 | 5.8563 | +0.1274 | $+1,681.45 | 60 |
| old_thin | 1.7617 | 1.8800 | +0.1183 | $+2,337.29 | 105 |

## Production Parity

This replay uses fields already present on accepted Companyfacts paper rows and known from SEC Companyfacts filed-date-safe fundamentals before the paper entry. No shared adapter, live/default orders, core ranking, core sizing, exits, LLM, or news path changed.

## Conclusion

Dual-growth pair support passed the three-window replay gate, but it is a historically adjacent Companyfacts dual-growth family; retain as a positive replay lead only until forward replacement-value rows justify shared adapter promotion.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 73 | $2,891.86 | 0.456608 |
| PLTR | 52 | $1,195.31 | 0.19287 |
| MU | 43 | $1,004.50 | 0.148845 |
| AMD | 15 | $758.48 | 0.10985 |
| GOOG | 14 | $154.16 | 0.045483 |
| AVGO | 16 | $-141.54 | 0.027923 |
| NFLX | 9 | $-5.50 | 0.012125 |
| NOW | 3 | $7.42 | 0.005827 |
| NVDA | 1 | $3.35 | 0.00047 |
| META | 3 | $-156.63 | 0.0 |
