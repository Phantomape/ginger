# exp-20260601-029: FINRA/IWM Cost-Liquidity Support

- decision: `accepted_shared_finra_iwm_cost_liquidity_support`
- aggregate EV: `6.6037` -> `6.6109` (+0.0072)
- aggregate PnL: `$200,837.01` -> `$201,151.57` (+314.56)
- incremental target trades: `34`
- max single positive share: `0.209295`
- positive PnL HHI: `0.148869`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.2214 | 4.2247 | +0.0033 | $+76.00 | 13 |
| mid_weak | 2.1785 | 2.1807 | +0.0022 | $+76.62 | 12 |
| old_thin | 0.2038 | 0.2055 | +0.0017 | $+161.94 | 9 |

## Production Parity

The same metadata/scalar is emitted by the shared FINRA/IWM default-off paper adapter (`quant/finra_iwm_paper_sleeve.py`) with focused parity coverage. Live/default orders remain disabled.

## Conclusion

FINRA/IWM cost-liquidity support passed Gate 4 and is retained in the shared default-off FINRA adapter without live/default order changes.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| SPOT | 4 | $88.34 | 0.209295 |
| DE | 6 | $102.12 | 0.181915 |
| CAT | 3 | $53.26 | 0.17055 |
| APP | 1 | $76.59 | 0.136437 |
| DDOG | 1 | $72.85 | 0.129774 |
| GS | 4 | $35.20 | 0.062936 |
| GE | 2 | $25.35 | 0.045158 |
| CRDO | 1 | $16.98 | 0.030248 |
| JPM | 2 | $9.71 | 0.020646 |
| CVX | 2 | $-7.59 | 0.007357 |
