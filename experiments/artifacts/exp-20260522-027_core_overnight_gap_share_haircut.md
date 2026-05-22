# exp-20260522-025 core_downside_path_haircut

## Hypothesis
Already-qualified core stock signals with top-quartile prior-20-day overnight-gap share are more event-driven and gap-risk exposed. A risk haircut should improve expected_value_score and tail risk without changing entry, exit, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_overnight_gap_share20_risk
- changed_variable: high_overnight_gap_share20_risk_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.6988
- EV delta: -0.1953
- PnL delta: -11400.99
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| overnight_gap_share20_haircut_000 | 0.0 | -2.6965 | -69836.65 | 0.0 | 33 | 52 | 0.276014 | False |
| overnight_gap_share20_haircut_025 | 0.25 | -0.9757 | -42996.94 | 0.0 | 31 | 45 | 0.329625 | False |
| overnight_gap_share20_haircut_050 | 0.5 | -0.5322 | -26499.25 | 0.0 | 31 | 46 | 0.238646 | False |
| overnight_gap_share20_haircut_075 | 0.75 | -0.1953 | -11400.99 | 0.0 | 31 | 45 | 0.280456 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.145 | -7034.46 | -0.0107 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0155 | 279.68 | 0.0 | 0.0 | 0.0 | -0.00141 |
| old_thin | -0.0658 | -4646.21 | -0.0103 | 0.05 | 0.0 | -0.012618 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move overnight_gap_share_20 feature, top-quartile state, and risk haircut into shared feature_layer/risk_engine/portfolio_engine with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
