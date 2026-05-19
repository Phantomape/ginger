# exp-20260505-005 Positionable Entry Planning

Decision: `rejected`

## Hypothesis

Candidates whose shared sizing result is zero shares should not consume scarce-slot planning priority; removing only those already non-positionable candidates before entry planning may improve capital allocation without changing signal thresholds, risk multipliers, or exits.

## Three-window deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | no_shares delta | slot_sliced delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | -9 | +0 |
| `mid_weak` | -0.0653 | -1461.62 | -0.05 | +0.0000 | -0.0238 | +1 | -11 | -1 |
| `old_thin` | -0.1469 | -8044.44 | -0.26 | +0.0000 | -0.0455 | +0 | -10 | -3 |

## Aggregate

- EV delta sum: `-0.2122` (-4.10%)
- PnL delta sum: `$-9,506.06` (-6.01%)
- no_shares delta sum: `-30`
- slot_sliced delta sum: `-4`

## Parity

No production code was changed by this experiment. If accepted, the rule must be implemented as a shared helper in production_parity.py and called by both backtester.py and run.py before entry planning.
