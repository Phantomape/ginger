# exp-20260505-013 Commodity State Trend Boost

Decision: `rejected`

## Hypothesis

If Commodities breadth is >=75% above 200MA and equal-weight 20-day sector return is >=5%, trend_long Commodity entries may carry enough convex continuation to justify a higher total risk budget than the current accepted 1.5x near-high sleeve.

## Gate 4

- passed: `False`
- best_variant: `commodity_state_total_2_5x`
- EV delta sum: `+0.2217` (+4.28%)
- PnL delta sum: `$+3,397.04` (+2.15%)
- EV windows improved/regressed: `1` / `0`
- touched candidate count: `12`

## Three-window Deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Touched |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.2217 | +3397.04 | +0.09 | -0.0002 | +0.0000 | +0 | 7 |
| `mid_weak` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 3 |
| `old_thin` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 2 |

## Production Parity

No production order path changed. A positive promotion requires a shared sector-state helper, a run.py adapter, and a parity test before live orders can change.
