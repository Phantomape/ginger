# exp-20260601-002: Companyfacts Share Contraction + RS Candidate Pool

- decision: `rejected_companyfacts_share_contraction_rs_candidate_pool`
- aggregate EV: `7.8941` -> `10.8418` (+2.9477)
- aggregate PnL: `$234,850.99` -> `$292,441.79` (+57,590.80)
- target trades: `124`
- max single positive share: `0.811479`
- positive PnL HHI: `0.671816`
- failed gates: `drawdown_drift_passed, concentration_guard_passed`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.5731 | +0.4103 | $+3,034.78 | 19 |
| mid_weak | 2.1402 | 3.0760 | +0.9358 | $+18,618.51 | 31 |
| old_thin | 0.5911 | 2.1927 | +1.6016 | $+35,937.51 | 74 |

## Conclusion

The share-contraction discriminator did not clear Gate 4, so no production or shared policy change is retained.

This scout used only filed-date Companyfacts share-count rows known on or before the signal date and the accepted frozen Fundamental Growth + RS paper rows. It made no live/default order, ranking, sizing, exit, LLM, news, or watchlist change.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| APP | 73 | $52,461.99 | 0.811479 |
| GOOG | 14 | $2,796.41 | 0.080817 |
| AMD | 11 | $5,321.62 | 0.079211 |
| NFLX | 9 | $-100.04 | 0.021543 |
| RTX | 14 | $-47.93 | 0.00695 |
| META | 3 | $-2,841.25 | 0.0 |
