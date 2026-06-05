# exp-20260605-004: SEC FTD + FINRA Excluding Form 4 Sale Pressure

- decision: `rejected_sec_ftd_finra_form4_sale_pressure_candidate_pool`
- aggregate EV vs core: `7.8941` -> `8.3361` (+0.4420)
- aggregate PnL delta vs core: `$+10,100.49`
- aggregate EV delta vs accepted FTD+FINRA: `+0.0000`
- aggregate PnL delta vs accepted FTD+FINRA: `$+0.00`
- target trades: `121`
- max single positive share: `0.240842`
- positive PnL HHI: `0.102311`
- failed gates: `accepted_ftd_finra_aggregate_ev_not_improved, accepted_ftd_finra_aggregate_pnl_not_improved`

## Three-Window Result

| window | EV core before | EV after | EV delta core | EV delta accepted | PnL delta accepted | target trades |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3853 | +0.2225 | +0.0000 | $+0.00 | 39 |
| mid_weak | 2.1402 | 2.1884 | +0.0482 | +0.0000 | $+0.00 | 40 |
| old_thin | 0.5911 | 0.7624 | +0.1713 | +0.0000 | $+0.00 | 42 |

## Conclusion

Gate 4 failed; the Form 4 sale-pressure exclusion did not produce a clean improvement versus the accepted FTD+FINRA comparator. No production or shared policy behavior is retained.

This is replay-only/default-off. It uses SEC FTD rows after publication lag, official FINRA rows after FINRA publication-date rules, Form 4 rows by usable_trade_date, and same-day/prior OHLCV. No production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

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
