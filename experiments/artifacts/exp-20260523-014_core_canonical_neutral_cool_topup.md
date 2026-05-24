# exp-20260523-014 core_canonical_neutral_cool_topup

## Hypothesis
A compressed entry-day canonical state vector may identify already-qualified core signals where leadership is neutral while portfolio/theme/regime risk heat is still cool. Those signals may deserve a small cap-aware risk top-up without changing entry, exit, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_canonical_neutral_cool_vector_topup
- changed_variable: canonical_neutral_leadership_cool_risk_topup_multiplier
- prior_trial_count: 1
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_compressed_context_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8962
- EV delta: 0.0021
- PnL delta: 27.36
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| canonical_neutral_cool_topup_1010 | 1.01 | 0.0021 | 27.36 | 0.0 | 6 | 3 | 1.0 | False |
| canonical_neutral_cool_topup_1025 | 1.025 | 0.0 | 49.6 | 0.0 | 8 | 8 | 0.994616 | False |
| canonical_neutral_cool_topup_1050 | 1.05 | -0.0009 | -19.83 | 0.0 | 13 | 15 | 0.990834 | False |
| canonical_neutral_cool_topup_1075 | 1.075 | -0.0011 | -69.95 | 0.0 | 13 | 15 | 0.986625 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.0026 | 55.55 | 0.0 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| old_thin | -0.0005 | -28.19 | 0.0004 | 0.0 | 0.0 | 0.000807 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move canonical vector state exposure and top-up into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
