# exp-20260601-027: Companyfacts Filing Timeliness Support

- decision: `accepted_companyfacts_filing_timeliness_support`
- aggregate EV: `12.6985` -> `13.0745` (+0.3760)
- aggregate PnL: `$300,134.87` -> `$305,514.70` (+5,379.83)
- incremental target trades: `265`
- max single positive share: `0.4065`
- positive PnL HHI: `0.236293`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | adjusted trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.7904 | 5.8610 | +0.0706 | $+959.55 | 70 |
| mid_weak | 5.3624 | 5.5629 | +0.2005 | $+2,300.31 | 90 |
| old_thin | 1.5457 | 1.6506 | +0.1049 | $+2,119.97 | 105 |

## Production Parity

The same rule is promoted through the shared default-off paper adapter (`quant/fundamental_growth_rs_paper_sleeve.py`). It changes no live/default orders, no production signal generation, no exits, and no LLM/news boundary.

## Conclusion

Filing timeliness support passed Gate 4 and is retained in the shared default-off paper adapter without live/default order changes.

## Top Positive Incremental Contributors

| ticker | trades | incremental PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 73 | $2,623.11 | 0.4065 |
| PLTR | 52 | $1,084.03 | 0.171695 |
| MU | 43 | $911.14 | 0.132491 |
| CRDO | 34 | $250.02 | 0.109802 |
| AMD | 15 | $687.96 | 0.097778 |
| GOOG | 14 | $139.82 | 0.040484 |
| AVGO | 16 | $-128.38 | 0.024856 |
| NFLX | 9 | $-5.02 | 0.01079 |
| NOW | 3 | $6.74 | 0.005186 |
| NVDA | 1 | $3.04 | 0.000419 |
