# exp-20260602-009: Companyfacts Sector-Residual Support

- decision: `positive_replay_lead_not_promoted_requires_shared_adapter`
- aggregate EV: `15.7099` -> `16.1444` (+0.4345)
- aggregate PnL: `$353,364.63` -> `$359,253.44` (+5,888.81)
- incremental target trades: `245`
- max single positive share: `0.4152`
- positive PnL HHI: `0.23963`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 7.2164 | 7.2995 | +0.0831 | $+1,065.87 | 68 |
| mid_weak | 5.7284 | 5.9392 | +0.2108 | $+2,372.24 | 83 |
| old_thin | 2.7651 | 2.9057 | +0.1406 | $+2,450.70 | 94 |

## Baseline Context

The current before-state is higher than the stored exp-20260601-030 artifact because the canonical core replay now includes the accepted exp-20260602-003 post-earnings continuation lift. The before/after comparison itself uses one code path and one three-window replay.

## Production Parity

Replay-only and default-off paper only. The test uses the persisted `broad_market_sector_map` cache plus fixed OHLCV snapshots and rows already selected by the accepted Companyfacts paper route. No live orders, shared production adapter, core ranking, sizing, exits, LLM, or news behavior changed.

## Conclusion

Sector-residual support passed the three-window alpha gate as a replay-only lead; a shared default-off adapter and parity tests are required before retention.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 67 | $2,877.47 | 0.4152 |
| PLTR | 46 | $1,054.18 | 0.155651 |
| MU | 41 | $998.65 | 0.135198 |
| CRDO | 34 | $270.07 | 0.110179 |
| AMD | 15 | $758.48 | 0.100332 |
| GOOG | 14 | $154.16 | 0.041542 |
| AVGO | 16 | $-141.54 | 0.025504 |
| NFLX | 9 | $-5.50 | 0.011074 |
| NOW | 1 | $41.52 | 0.005322 |
| META | 2 | $-118.67 | 0.0 |
