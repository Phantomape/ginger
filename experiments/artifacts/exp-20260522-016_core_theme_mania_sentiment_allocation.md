# exp-20260522-016 core_theme_mania_sentiment_allocation

## Hypothesis
Core stock signals in the theme_mania sentiment surface may be crowded enough to deserve a risk haircut, or strong enough to deserve a small top-up. A single cap-aware multiplier should improve EV without changing entry filters, ranking, exits, universe, LLM, or news logic.

## Trial accounting
- trial_family: core_sentiment_surface_theme_mania_risk
- changed_variable: sentiment_surface_theme_mania_risk_multiplier
- prior_trial_count: 3
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 6.7403
- EV delta: -1.1538
- PnL delta: -33553.83
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| theme_mania_haircut_0900 | 0.9 | -1.1538 | -33553.83 | -0.0087 | 73 | 71 | 0.124875 | False |
| theme_mania_haircut_0950 | 0.95 | -1.1701 | -32173.96 | -0.0046 | 73 | 71 | 0.124912 | False |
| theme_mania_topup_1025 | 1.025 | -1.209 | -30305.13 | 0.0014 | 47 | 58 | 0.127993 | False |
| theme_mania_topup_1050 | 1.05 | -1.2131 | -29602.63 | 0.0033 | 54 | 59 | 0.127136 | False |

## Selected window deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.8423 | -19321.81 | -0.0131 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.2093 | -7377.98 | -0.0087 | 0.0 | 0.0 | 1.5e-05 |
| old_thin | -0.1022 | -6854.04 | -0.0105 | 0.05 | 0.0 | 0.006027 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move sentiment-surface theme_mania state and risk multiplier into shared sentiment_surface/portfolio_engine plumbing with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
