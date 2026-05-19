# exp-20260511-107 RS20 Entry-State Regime Scope

Decision: `rejected_rs20_entry_state_regime_scope`
Best variant: `exclude_defensive`

## Hypothesis

The accepted RS20 entry-state 1.10x top-up may be weaker in defensive or non-risk-on regime-exit buckets; restricting the existing top-up by regime scope could improve risk-adjusted EV without changing the RS20 threshold, multiplier, entries, exits, ranking, candidate pool, or LLM boundary.

## Aggregate

| Variant | EV delta | PnL delta | Windows EV +/- | Touched trades | Suppressed signals | Max DD change | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| exclude_defensive | 0.0012 | 82.21 | 1/0 | 1 | 2 | 0.0 | FAIL |
| risk_on_only | -0.0377 | -363.77 | 1/1 | 2 | 5 | 0.0 | FAIL |

## Window Deltas

| Variant | Window | EV delta | PnL delta | Return delta | Sharpe delta | DD delta | Survival delta |
|---|---|---:|---:|---:|---:|---:|---:|
| exclude_defensive | late_strong | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| exclude_defensive | mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| exclude_defensive | old_thin | 0.0012 | 82.21 | 0.0009 | 0.0 | 0.0 | 0.0 |
| risk_on_only | late_strong | -0.0389 | -445.98 | -0.0045 | -0.02 | 0.0 | 0.0 |
| risk_on_only | mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| risk_on_only | old_thin | 0.0012 | 82.21 | 0.0009 | 0.0 | 0.0 | 0.0 |

## Decision

Rejected: scoping the accepted RS20 entry-state top-up by regime bucket did not clear the three-window Gate 4 criteria, so the shared RS20 policy remains unchanged and nearby regime-scope variants should not be retried without new evidence.

## Production Impact

Replay-only experiment. No shared policy, run adapter, backtester adapter, orders, exits, ranking, filters, LLM boundary, or universe membership changed.
