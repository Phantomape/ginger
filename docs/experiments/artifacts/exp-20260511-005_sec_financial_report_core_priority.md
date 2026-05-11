# exp-20260511-005 SEC Financial-Report Core Priority

Decision: `rejected`.

Hypothesis: core A/B signals with an active non-platform SEC financial-report positive T+1 excess-drift label may deserve entry-planning priority over untagged survived signals.

| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Tagged days | Changed trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2340 | 4.2340 | +0.0000 | $94,086.91 | $94,086.91 | $+0.00 | 3 | 0 |
| mid_weak | 1.6689 | 1.6689 | +0.0000 | $61,813.40 | $61,813.40 | $+0.00 | 5 | 0 |
| old_thin | 0.3853 | 0.2513 | -0.1340 | $28,544.11 | $20,770.20 | $-7,773.91 | 9 | 16 |

Protocol: `docs/backtesting.md` canonical three-window fixed-snapshot replay.

Single causal variable: event-conditioned entry-planning priority for already-survived core signals. No SEC thresholds, event families, hold days, sizing, exits, add-ons, universe membership, LLM/news replay, or live orders changed.

Production impact: replay-only scout. A positive result would require a shared production/backtest event-priority helper and parity tests before any live/default behavior could change.
