# exp-20260505-017 Financials Leader Add-on Cap

Decision: `rejected`

## Hypothesis

Accepted trend_long Financials sector leaders already receive a 2.5x risk budget, but initial-cap increases were too small and riskier. If a Financials leader survives to the existing day-2 follow-through checkpoint, raising only the first add-on cap may increase convex winner capture without changing entry, exit, ranking, universe, or LLM/news behavior.

## Gate 4

- passed: `False`
- best_variant: `financials_leader_addon_cap_60pct`
- EV delta sum: `+0.0000` (+0.00%)
- PnL delta sum: `$+0.00` (+0.00%)
- EV windows improved/regressed: `0` / `0`
- Financials leader add-on events: `3`

## Three-window Deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Add-on exec delta | Events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | +0 | 0 |
| `mid_weak` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | +0 | 2 |
| `old_thin` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | +0 | 1 |

## Production Parity

Replay-only. A positive result requires a shared Financials-leader add-on cap helper and parity test before production orders change.
