# exp-20260601-026: Companyfacts Gross-Margin + RS Adapter

- decision: `accepted_shared_companyfacts_gross_margin_rs_adapter`
- aggregate EV: `6.3596` -> `12.6985` (+6.3389)
- aggregate PnL: `$192,538.61` -> `$300,134.87` (+107,596.26)
- target trades: `265`
- max single positive share: `0.4065`
- positive PnL HHI: `0.236292`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 5.7904 | +1.6822 | $+19,190.34 | 70 |
| mid_weak | 2.1405 | 5.3624 | +3.2219 | $+46,006.89 | 90 |
| old_thin | 0.1109 | 1.5457 | +1.4348 | $+42,399.03 | 105 |

## Production Parity

The retained behavior lives in `quant/fundamental_growth_rs_paper_sleeve.py`, which is already called by production `run.py`. It is default-off paper state only: `trade_enabled=false`, no live/default orders, no core ranking, no core sizing, no exits, and no LLM/news boundary changes.

## Conclusion

Gross-margin quality passed all three PIT-DTE windows and is now retained as a shared default-off production-visible paper adapter; live/default orders, core ranking, sizing, exits, LLM, and news remain unchanged.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 73 | $52,461.99 | 0.4065 |
| PLTR | 52 | $21,680.62 | 0.171695 |
| MU | 43 | $18,222.17 | 0.132489 |
| CRDO | 34 | $5,000.51 | 0.109802 |
| AMD | 15 | $13,759.33 | 0.097779 |
| GOOG | 14 | $2,796.41 | 0.040484 |
| AVGO | 16 | $-2,567.60 | 0.024855 |
| NFLX | 9 | $-100.04 | 0.010791 |
| NOW | 3 | $134.72 | 0.005186 |
| NVDA | 1 | $60.72 | 0.000418 |
