# exp-20260524-013 core_low_theme_component_topup

## Hypothesis
The new point-in-time component attribution shows low theme_participation already-filled core trades had higher average realized PnL in all three canonical windows. A low theme-participation state may identify less-crowded core entries that deserve a small cap-aware top-up without changing entries, exits, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_low_theme_participation_component_topup
- changed_variable: low_theme_participation_post_sizing_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: high
- new_evidence_type: new_pit_component_attribution_readout

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.885
- EV delta: -0.0091
- PnL delta: 1370.01
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| low_theme_component_topup_1025 | 1.025 | -0.0183 | 537.29 | 0.0016 | 6 | 14 | 0.539107 | False |
| low_theme_component_topup_1050 | 1.05 | -0.0091 | 1370.01 | 0.0035 | 6 | 18 | 0.513375 | False |
| low_theme_component_topup_1075 | 1.075 | -0.0199 | 1972.25 | 0.0051 | 6 | 20 | 0.358661 | False |
| low_theme_component_topup_1100 | 1.1 | -0.0326 | 2809.25 | 0.0082 | 7 | 23 | 0.34562 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.0036 | 714.72 | 0.0019 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.0055 | 655.29 | 0.0035 | 0.0 | 0.0 | 0.016296 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move the theme_participation component field and risk policy into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
