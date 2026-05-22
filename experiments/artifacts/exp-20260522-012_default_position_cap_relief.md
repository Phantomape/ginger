# exp-20260522-012 default_position_cap_relief

## Hypothesis
Default cap-bound core entries may be underallocated after the accepted narrow cap/risk overlays; modestly relaxing the default single-position cap could increase expected value without changing entries, exits, ranking, candidate pool, LLM authority, or filters.

## Trial accounting
- trial_family: core_default_position_cap_relief
- changed_variable: default_max_position_pct
- prior_trial_count: 5
- multiple_testing_risk_bucket: high
- new_evidence_type: cap_bound_core_trade_diagnostics

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 8.0873
- EV delta: 0.1932
- PnL delta: 3387.2
- decision: rejected_failed_gate4

## Sweep summary
| variant | cap | EV delta | PnL delta | DD delta | improved | regressed | changed | passed |
|---|---:|---:|---:|---:|---|---|---:|---|
| default_cap_0525 | 0.525 | 0.133 | 1815.27 | 0.001 | late_strong | mid_weak,old_thin | 12 | False |
| default_cap_0550 | 0.55 | 0.1669 | 2402.96 | 0.0017 | late_strong,mid_weak | old_thin | 13 | False |
| default_cap_0575 | 0.575 | 0.1932 | 3387.2 | 0.0017 | late_strong,mid_weak | old_thin | 16 | False |

## Window deltas for selected variant
| window | EV | PnL | DD | survival |
|---|---:|---:|---:|---:|
| late_strong | 0.1838 | 2540.52 | 0.0 | 0.0 |
| mid_weak | 0.02 | 1022.68 | 0.0017 | 0.0 |
| old_thin | -0.0106 | -176.0 | 0.0004 | 0.0 |

## Production impact
```text
{
  "backtester_adapter_changed": false,
  "live_default_orders_changed": false,
  "notes": "No strategy behavior changed. The cap values were tested by a local monkey patch only; no positive result is kept without shared policy promotion.",
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Decision
Best variant failed Gate 4 because at least one fixed window regressed in EV; do not promote a broad default cap retune from mixed-window evidence.

## Next evidence needed
Do not retry broad default cap values on the same fixed sample. If this mechanism is revisited, use a new production-visible cap-bound quality state that avoids old_thin V-style loser amplification and promote only through shared constants/policy with a parity test.
