# exp-20260523-013 core_canonical_leadership_risk_topup

## Hypothesis
A compressed entry-day canonical state vector may identify already-qualified core signals where leadership is strong while portfolio/theme/regime risk heat is still cool. Those signals may deserve a small cap-aware risk top-up without changing entry, exit, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_canonical_leadership_risk_vector_topup
- changed_variable: canonical_strong_leadership_cool_risk_topup_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_compressed_context_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8821
- EV delta: -0.012
- PnL delta: 205.29
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| canonical_leadership_cool_topup_1025 | 1.025 | -0.012 | 205.29 | 0.0 | 10 | 9 | 0.958624 | False |
| canonical_leadership_cool_topup_1050 | 1.05 | -0.0253 | 472.99 | 0.0 | 11 | 11 | 0.670033 | False |
| canonical_leadership_cool_topup_1075 | 1.075 | -0.0254 | 691.97 | 0.0 | 11 | 13 | 0.870808 | False |
| canonical_leadership_cool_topup_1100 | 1.1 | -0.0391 | 870.74 | 0.0 | 12 | 12 | 0.710162 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.0103 | 296.97 | 0.0009 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.0005 | -18.68 | 0.0 | 0.0 | 0.0 | 0.002069 |
| old_thin | -0.0012 | -73.0 | 0.0008 | 0.0 | 0.0 | 0.002155 |

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
