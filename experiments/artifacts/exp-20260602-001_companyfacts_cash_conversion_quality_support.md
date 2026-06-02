# exp-20260602-001: Companyfacts Cash-Conversion Quality Support

- decision: `positive_replay_lead_not_promoted_requires_forward_rows`
- aggregate EV: `13.4753` -> `13.8842` (+0.4089)
- aggregate PnL: `$311,052.25` -> `$316,808.41` (+5,756.16)
- incremental target trades: `230`
- max single positive share: `0.459363`
- positive PnL HHI: `0.286255`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.9847 | 6.1388 | +0.1541 | $+1,636.92 | 66 |
| mid_weak | 5.7289 | 5.8558 | +0.1269 | $+1,673.81 | 68 |
| old_thin | 1.7617 | 1.8896 | +0.1279 | $+2,445.43 | 96 |

## Production Parity

This replay uses SEC Companyfacts rows with filed dates on or before the signal date. It does not change shared production/backtest policy, live orders, core ranking, sizing, exits, LLM, or news behavior. Any future promotion requires a shared default-off adapter and parity tests.

## Conclusion

Cash-conversion quality support passed the three-window replay gate, but it is a nearby Companyfacts support field and is not promoted without closed forward replacement-value rows and a shared adapter parity pass.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 73 | $2,891.86 | 0.459363 |
| PLTR | 52 | $1,195.31 | 0.194034 |
| MU | 43 | $1,004.50 | 0.149743 |
| AMD | 15 | $758.48 | 0.110513 |
| GOOG | 14 | $154.16 | 0.045757 |
| AVGO | 16 | $-141.54 | 0.028092 |
| CRDO | 10 | $39.26 | 0.006164 |
| NOW | 3 | $7.42 | 0.005862 |
| NVDA | 1 | $3.35 | 0.000473 |
| META | 3 | $-156.63 | 0.0 |
