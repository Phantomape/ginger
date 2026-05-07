# exp-20260505-012 Compound Severe-haircut Skip

Decision: `rejected`

## Hypothesis

Candidates with multiple independent severe 0.25x risk haircuts may be too low quality for scarce entry slots. Treating only the compound severe-haircut cohort as no-trade could improve EV while preserving single-haircut winners that prior audits kept alive.

## Gate 4

- passed: `False`
- best_variant: `compound_2plus_025x_skip`
- EV delta sum: `+0.1883` (+3.64%)
- PnL delta sum: `$-4,063.71` (-2.57%)
- EV windows improved/regressed: `2` / `1`
- skipped candidate count: `17`

## Three-window Deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Skipped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0009 | +20.93 | +0.00 | +0.0000 | +0.0438 | -1 | 3 |
| `mid_weak` | +0.2319 | -2226.43 | +0.55 | -0.0420 | +0.1233 | -4 | 6 |
| `old_thin` | -0.0445 | -1858.21 | -0.09 | +0.0000 | +0.0409 | -2 | 8 |

## Production Parity

No production order path changed. A positive retry would need a shared policy helper, a run.py adapter that exposes the skip reason, and a parity test.
