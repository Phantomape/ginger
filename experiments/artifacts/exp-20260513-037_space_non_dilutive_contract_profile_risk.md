# exp-20260513-037 Space non-dilutive contract profile risk

## Hypothesis
On top of accepted exp-032 Space attention overlay stack, official Space signals with production registry profiles tied to contracts or revenue quality but not financing/dilution sensitivity may have cleaner catalyst duration. A single risk scalar can test whether that profile deserves more or less capital without changing the Space pool, ranking, events, targets, stops, LLM boundary, or live slots.

## Single Changed Variable
`space_non_dilutive_contract_profile_scalar` applied after the accepted exp-032 attention-overlay stack.

## Gate 4 Summary
- Decision: `rejected`
- Best scalar: `1.15`
- Aggregate delta vs exp-032: EV `0.181900`, PnL `4480.41`
- Profile signals changed: `9` of `11` eligible

## Three-Window Deltas vs Exp-032
| window | EV delta | PnL delta | max DD delta | trades | survival | profile signals |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.000000 | 0.00 | 0.000000 | 20 | 0.706900 | 2 |
| mid_weak | -0.024200 | -37.03 | 0.000000 | 23 | 0.653300 | 5 |
| old_thin | 0.206100 | 4517.44 | -0.001400 | 25 | 0.733300 | 4 |

## Sweep
| scalar | gate | dEV | dPnL | EV-improved windows | EV-regressed windows | changed signals |
|---:|---|---:|---:|---:|---:|---:|
| 0.750 | fail | -0.357800 | -7327.97 | 1 | 1 | 9 |
| 0.900 | fail | -0.142900 | -2946.13 | 1 | 1 | 9 |
| 1.000 | fail | +0.000000 | +0.00 | 0 | 0 | 0 |
| 1.025 | fail | +0.033300 | +724.93 | 1 | 0 | 9 |
| 1.050 | fail | +0.068300 | +1517.70 | 1 | 1 | 9 |
| 1.075 | fail | +0.101600 | +2235.72 | 1 | 1 | 9 |
| 1.100 | fail | +0.113200 | +2991.43 | 1 | 1 | 9 |
| 1.150 | fail | +0.181900 | +4480.41 | 1 | 1 | 9 |

## Production Impact
No shared production policy was changed by this experiment artifact. If accepted, the scalar must be promoted into `quant/space_catalyst_sleeve.py` and covered by parity tests before live use.
