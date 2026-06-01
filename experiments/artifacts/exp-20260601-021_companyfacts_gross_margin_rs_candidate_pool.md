# exp-20260601-021: Companyfacts Gross-Margin + RS Candidate Pool

- decision: `positive_replay_lead_not_promoted_baseline_mismatch`
- aggregate EV: `6.3596` -> `12.6985` (+6.3389)
- aggregate PnL: `$192,538.61` -> `$300,134.87` (+107,596.26)
- target trades: `265`
- max single positive share: `0.4065`
- positive PnL HHI: `0.236292`
- failed gates: `baseline_matches_docs_for_retention`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 5.7904 | +1.6822 | $+19,190.34 | 70 |
| mid_weak | 2.1405 | 5.3624 | +3.2219 | $+46,006.89 | 90 |
| old_thin | 0.1109 | 1.5457 | +1.4348 | $+42,399.03 | 105 |

## Conclusion

The gross-margin quality field passed alpha checks, but current replay baseline drift blocks retention or promotion.

This scout used only SEC Companyfacts rows filed on or before the signal date. It made no live/default order, ranking, sizing, exit, LLM, news, or watchlist change.

## Baseline Caveat

Current replay baseline differs from docs/backtesting.md accepted baseline; positive replay evidence cannot be retained or promoted until parity is resolved.

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
