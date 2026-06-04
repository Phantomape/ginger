# exp-20260604-026: SEC FTD + FINRA Confirmed Candidate Pool

- decision: `positive_replay_lead_not_promoted_requires_ftd_finra_shared_adapter`
- aggregate EV: `7.8941` -> `8.3361` (+0.4420)
- aggregate PnL delta: `$+10,100.49`
- target trades: `121`
- max single positive share: `0.240842`
- positive PnL HHI: `0.102311`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3853 | +0.2225 | $+2,867.33 | 39 |
| mid_weak | 2.1402 | 2.1884 | +0.0482 | $+2,052.72 | 40 |
| old_thin | 0.5911 | 0.7624 | +0.1713 | $+5,180.44 | 42 |

## Conclusion

Gate 4 passed, but FTD+FINRA remains replay-only until a shared default-off adapter implements the same PIT source policies in production and backtest.

The tested fields are SEC FTD rows after conservative publication lag, official FINRA rows after FINRA publication-date rules, and same-day/prior OHLCV. The result is replay-only/default-off: no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| IONQ | 6 | $5,785.57 | 0.240842 |
| ASTS | 6 | $3,265.71 | 0.135945 |
| HUT | 2 | $2,140.15 | 0.08909 |
| UUUU | 2 | $2,039.85 | 0.084915 |
| KNX | 3 | $1,043.65 | 0.043445 |
| CG | 3 | $1,042.25 | 0.043387 |
| LRN | 2 | $847.40 | 0.035276 |
| AM | 3 | $764.55 | 0.031827 |
| ALB | 1 | $718.89 | 0.029926 |
| OVV | 2 | $679.11 | 0.02827 |
