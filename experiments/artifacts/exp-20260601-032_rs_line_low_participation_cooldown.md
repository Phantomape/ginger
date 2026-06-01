# exp-20260601-032: RS-line Low Participation Cooldown

- decision: `rejected_rs_line_low_participation_cooldown_candidate_pool`
- aggregate EV: `6.3596` -> `6.6844` (+0.3248)
- aggregate PnL: `$192,538.61` -> `$198,858.72` (+6,320.11)
- target trades: `22`
- max single positive share: `0.450114`
- positive PnL HHI: `0.26707`
- failed gates: `drawdown_drift_passed`

## Three-Window Result

| window | target trades | target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3 | $1,204.92 | 4.1082 | 4.2288 | +0.1206 | $+1,204.92 | -0.0005 |
| mid_weak | 11 | $3,244.31 | 2.1405 | 2.3188 | +0.1783 | $+3,244.31 | -0.0015 |
| old_thin | 8 | $1,870.88 | 0.1109 | 0.1368 | +0.0259 | $+1,870.88 | +0.0166 |

## Production Parity

This replay uses OHLCV volume participation and same-ticker de-clustering on already persisted default-off RS-line paper rows. No shared adapter, live/default orders, core signal generation, ranking, sizing, exits, LLM, news, or watchlist path changed. Promotion would require a shared production-visible adapter plus backtest/production parity tests.

## Conclusion

Gate 4 failed, so no strategy, production, or shared adapter change is retained.

## Top Positive Incremental Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 7 | $5,002.01 | 0.450114 |
| CRDO | 4 | $1,289.09 | 0.182809 |
| GOOG | 1 | $1,034.26 | 0.076064 |
| RTX | 1 | $523.98 | 0.038536 |
| MU | 3 | $410.40 | 0.119044 |
| NOW | 2 | $376.12 | 0.04796 |
| COIN | 1 | $-352.20 | 0.0 |
| PLTR | 3 | $-1,963.55 | 0.085473 |

No JavaScript was used.
