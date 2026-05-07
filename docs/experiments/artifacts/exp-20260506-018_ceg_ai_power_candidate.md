# exp-20260506-018 CEG AI Power Infrastructure Candidate

Decision: `rejected`

## Hypothesis

CEG may capture AI datacenter power demand as a more contracted power-generation infrastructure candidate than prior speculative power or datacenter baskets. Adding only CEG tests whether this specific power-infrastructure leg adds stable replacement value to the existing A/B trend and breakout engine without broad ticker noise.

## Candidate

`CEG`

## Three-window deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | CEG trades | CEG PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 0 | +0.00 |
| `mid_weak` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 0 | +0.00 |
| `old_thin` | -0.0511 | -2222.10 | -0.10 | -0.0001 | -0.0178 | +1 | 1 | -2147.64 |

## Aggregate

- EV delta sum: `-0.0511` (-1.00%)
- PnL delta sum: `$-2,222.10` (-1.42%)
- EV windows improved/regressed: `0` / `1`
- CEG trade count / PnL: `1` / `$-2,147.64`

## Parity

No production universe or order path changed. CEG promotion would need universe governance or a default-off pilot adapter before live orders.

## Decision Note

If accepted, route CEG through default-off governance instead of core promotion. If rejected, do not mine more AI-power single-name variants without new ex-ante evidence.
