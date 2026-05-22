# exp-20260522-025 core_downside_path_haircut

## Hypothesis
Already-qualified core stock signals with top-quartile prior-20-day downside-path share are more fragile/choppy continuation paths. A risk haircut should improve expected_value_score and tail risk without changing entry, exit, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_downside_path_share20_risk
- changed_variable: downside_path_share20_top_quartile_risk_multiplier
- prior_trial_count: 2
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8941
- EV delta: 0.0
- PnL delta: 0.0
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| downside_share20_haircut_000 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| downside_share20_haircut_025 | 0.25 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| downside_share20_haircut_050 | 0.5 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| downside_share20_haircut_075 | 0.75 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move downside_path_share_20 feature, top-quartile state, and risk haircut into shared feature_layer/risk_engine/portfolio_engine with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed adjusted-signal sample guard; the top-quartile downside-path state did not touch any sized core signals across the three standard windows.
