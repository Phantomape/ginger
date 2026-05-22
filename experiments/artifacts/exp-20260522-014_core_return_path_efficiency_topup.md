# exp-20260522-014 core_return_path_efficiency_topup

## Hypothesis
Core stock signals with top-quartile 20-day return-path efficiency may represent smoother trend accumulation than spike-driven moves. A small cap-aware risk top-up should improve EV without changing entry filters, ranking, exits, universe, LLM, or news logic.

## Trial accounting
- trial_family: core_daily_return_path_efficiency_risk
- changed_variable: return_path_efficiency20_top_quartile_risk_multiplier
- prior_trial_count: 1
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8723
- EV delta: -0.0218
- PnL delta: 456.33
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| efficiency20_topup_1025 | 1.025 | -0.0218 | 456.33 | 0.0016 | 10 | 14 | 0.541838 | False |
| efficiency20_topup_1050 | 1.05 | -0.0257 | 1269.7 | 0.0035 | 13 | 19 | 0.821099 | False |
| efficiency20_topup_1075 | 1.075 | -0.0236 | 1886.44 | 0.0051 | 13 | 22 | 0.359863 | False |
| efficiency20_topup_1100 | 1.1 | -0.0296 | 2981.51 | 0.0082 | 17 | 27 | 0.403995 | False |

## Selected window deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.0111 | 279.27 | 0.0009 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.0107 | 177.06 | 0.0016 | 0.0 | 0.0 | 0.014452 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move return_path_efficiency_20 feature, top-quartile state, and risk top-up into shared feature_layer/risk_engine/portfolio_engine with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
