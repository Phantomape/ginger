# exp-20260510-022 Dust Slot Pre-Plan Filter

Decision: `rejected`

## Hypothesis

Signals that the accepted sizing stack already reduces to dust-sized whole-share orders may have poor slot opportunity cost; removing only those dust-sized orders before scarce slot planning may improve EV by letting meaningful candidates compete for slots.

## Gate 4

- passed: `False`
- best_variant: `drop_one_or_two_share_sized_signals`
- aggregate EV delta: `-0.0510` (-0.81%)
- aggregate PnL delta: `$-2,173.70` (-1.18%)
- EV windows improved/regressed: `2` / `1`
- filtered candidate count: `6`

## Three-window Deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | Trades delta | Survival after | Filtered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0010 | +20.93 | +0.00 | +0.0000 | -1 | 0.8039 | 2 |
| `mid_weak` | +0.0024 | +87.50 | +0.00 | +0.0000 | -2 | 0.7925 | 2 |
| `old_thin` | -0.0544 | -2282.13 | -0.09 | -0.0001 | +0 | 0.9333 | 2 |

## Production Impact

- Replay-only runtime patch; no live/default orders changed.
- A positive result would need the exact helper in shared `production_parity.py`, plus run/backtester parity tests.
