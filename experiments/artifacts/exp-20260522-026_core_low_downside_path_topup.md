# exp-20260522-026 core_low_downside_path_topup

## Hypothesis
Already-qualified core stock signals with bottom-quartile prior-20-day downside-path share have cleaner trend persistence. A small cap-aware risk top-up should improve expected_value_score without changing entry, exit, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_low_downside_path_share20_risk
- changed_variable: low_downside_path_share20_bottom_quartile_risk_multiplier
- prior_trial_count: 3
- multiple_testing_risk_bucket: high
- new_evidence_type: opposite_side_after_zero_touch

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8803
- EV delta: -0.0138
- PnL delta: 1258.69
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| low_downside_share20_topup_1025 | 1.025 | -0.0186 | 481.99 | 0.0016 | 17 | 17 | 0.538474 | False |
| low_downside_share20_topup_1050 | 1.05 | -0.0138 | 1258.69 | 0.0035 | 20 | 23 | 0.512133 | False |
| low_downside_share20_topup_1075 | 1.075 | -0.0249 | 1813.93 | 0.0051 | 20 | 26 | 0.357646 | False |
| low_downside_share20_topup_1100 | 1.1 | -0.0299 | 2874.17 | 0.0082 | 24 | 31 | 0.311365 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.0018 | 754.55 | 0.0019 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.0058 | 654.58 | 0.0035 | 0.0 | 0.0 | 0.016078 |
| old_thin | -0.0062 | -150.44 | 0.0015 | 0.0 | 0.0 | 0.004154 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move downside_path_share_20 feature, bottom-quartile state, and cap-aware top-up into shared feature_layer/risk_engine/portfolio_engine with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
