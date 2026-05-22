# exp-20260522-013 core_max_daily_return20_haircut

## Hypothesis
Core signals whose prior 20 trading days contain a top-quartile single-day return may be crowded / lottery-like continuation paths. A risk haircut should improve EV and tail risk without changing entry filters, ranking, exits, universe, LLM, or news logic.

## Trial accounting
- trial_family: core_daily_return_path_max20_risk
- changed_variable: max_daily_return20_top_quartile_risk_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.6646
- EV delta: -0.2295
- PnL delta: -17709.69
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| max20_haircut_000 | 0.0 | -3.0881 | -107520.74 | -0.0413 | 77 | 67 | 0.221328 | False |
| max20_haircut_025 | 0.25 | -1.2349 | -68032.47 | -0.0569 | 52 | 60 | 0.168577 | False |
| max20_haircut_050 | 0.5 | -0.6545 | -41979.73 | -0.0426 | 52 | 56 | 0.204013 | False |
| max20_haircut_075 | 0.75 | -0.2295 | -17709.69 | -0.0217 | 52 | 57 | 0.189556 | False |

## Selected window deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.0338 | -4102.79 | -0.0105 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.2127 | -9265.48 | -0.0217 | 0.0 | 0.0 | -0.00365 |
| old_thin | -0.0506 | -4341.42 | -0.0159 | 0.05 | 0.0 | -0.043921 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move max_daily_return_20_pct feature, top-quartile state, and risk haircut into shared feature_layer/risk_engine/portfolio_engine with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
