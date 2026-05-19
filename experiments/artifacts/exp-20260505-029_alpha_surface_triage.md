# exp-20260505-029 Alpha Surface Triage

Status: accepted direction, no strategy change.

This run was an alpha search, not a bug fix. The goal was to decide what alpha direction is worth optimizing after reading `AGENTS.md`, `docs/backtesting.md`, `docs/alpha-optimization-playbook.md`, recent `experiments` logs, and the current three-window baseline.

## Baseline

The canonical three-window production-equivalent baseline was rechecked:

| Window | Date range | EV | SharpeD | PnL | Max DD | Win rate | Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 2025-10-23 -> 2026-04-21 | 3.4191 | 4.35 | 78600.33 | 5.41% | 78.95% | 19 |
| mid_weak | 2025-04-23 -> 2025-10-22 | 1.4415 | 2.62 | 55015.08 | 8.79% | 52.38% | 21 |
| old_thin | 2024-10-02 -> 2025-04-22 | 0.3179 | 1.29 | 24642.07 | 8.05% | 40.91% | 22 |

## Alpha Direction Decision

Current strongest alpha direction: keep optimizing the default-off external event overlay bundle, but only through forward replacement-value evidence. Do not promote it to live capital yet.

Rationale:

- `exp-20260504-049` and `exp-20260505-025` showed the event overlay bundle improved EV and PnL in all three canonical windows.
- `exp-20260505-026` showed the candidate pool has broad positive forward-return shape, but same-day replacement value is not strong enough for live promotion.
- `exp-20260505-027` found the LLM soft-ranking lane has no baseline ranking-eligible aligned LLM samples, so forcing an LLM-ranking experiment now would be fake precision.
- Recent core A/B retunes across ranking, target, stop, sizing, add-on, and universe surfaces were rejected or no-op. Repeating nearby variants would violate the mechanism insight guardrails.

## Non-Actions

No signal generation, sizing, ranking, entry, exit, universe, add-on, LLM, or production-order behavior changed.

The main risk in forcing a code change now is overfitting residual losses that are already small or already de-risked, while damaging the accepted SPY-relative leader and trend/breakout core.

## Next Evidence Needed

Before live promotion of the event overlay, require closed forward paper outcomes and replacement-value attribution across at least two sources. If another alpha search must run before then, it needs a genuinely new external source or a new ex-ante candidate discriminator with nonzero coverage.
