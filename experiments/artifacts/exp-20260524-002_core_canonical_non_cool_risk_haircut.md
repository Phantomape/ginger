# exp-20260524-002 core_canonical_non_cool_risk_haircut

## Hypothesis
A compressed entry-day canonical risk-heat vector may identify already-qualified core stock signals where portfolio/theme/regime heat is not cool. A bounded non-cool risk haircut may improve expected_value_score or tail risk without changing entry, exit, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_canonical_non_cool_risk_heat_haircut
- changed_variable: canonical_non_cool_risk_heat_haircut_multiplier
- prior_trial_count: 2
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_compressed_context_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.7689
- EV delta: -0.1252
- PnL delta: -3836.28
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| non_cool_risk_heat_haircut_090 | 0.9 | -0.1252 | -3836.28 | -0.0085 | 11 | 26 | 0.315488 | False |
| non_cool_risk_heat_haircut_075 | 0.75 | -0.3907 | -11365.42 | -0.0118 | 11 | 33 | 0.24022 | False |
| non_cool_risk_heat_haircut_050 | 0.5 | -0.889 | -23749.68 | -0.0118 | 11 | 36 | 0.227476 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.055 | -724.4 | 0.0001 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.0702 | -3111.88 | -0.0085 | 0.0 | 0.0 | 0.008328 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move canonical risk-heat state exposure and the haircut into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
