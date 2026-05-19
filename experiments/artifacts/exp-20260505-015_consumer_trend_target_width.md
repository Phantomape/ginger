# exp-20260505-015 Consumer Trend Target Width

Decision: `rejected`

## Hypothesis

`trend_long | Consumer Discretionary` winners may be target-clipped by the current regime-aware target path. A modest 5.0-5.5 ATR target could improve winner capture without changing entries, sizing, candidate pool, or LLM/news behavior.

## Gate 4

- passed: `False`
- best_variant: `consumer_trend_target_5_5atr`
- EV delta sum: `+0.0497` (+0.96%)
- PnL delta sum: `$+2,183.69` (+1.38%)
- EV windows improved/regressed: `1` / `0`
- touched candidate count: `9`

## Three-window Deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Touched |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 2 |
| `mid_weak` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 0 |
| `old_thin` | +0.0497 | +2183.69 | +0.08 | -0.0001 | +0.0000 | +0 | 7 |

## Production Parity

No production order path changed. A positive promotion requires a shared target-width constant/helper and a parity test before live orders can change.
