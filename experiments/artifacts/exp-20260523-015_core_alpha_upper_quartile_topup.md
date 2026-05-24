# exp-20260523-015 core_alpha_upper_quartile_topup

## Hypothesis
The entry-day continuous alpha score has little discrimination inside already-filled core trades because most are top decile, but the remaining top-quartile bucket had strong two-window historical contribution. A small cap-aware top-up for already selected non-ETF/non-Commodity top-quartile core signals may improve EV without changing entries, exits, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_alpha_score_bucket_top_quartile_topup
- changed_variable: alpha_score_top_quartile_post_sizing_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_compressed_context_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8899
- EV delta: -0.0042
- PnL delta: -38.98
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| alpha_upper_quartile_topup_1025 | 1.025 | -0.0042 | -38.98 | 0.0 | 4 | 5 | 0.768581 | False |
| alpha_upper_quartile_topup_1050 | 1.05 | -0.0047 | -94.79 | 0.0 | 5 | 6 | 0.869171 | False |
| alpha_upper_quartile_topup_1075 | 1.075 | -0.0049 | -138.1 | 0.0 | 5 | 6 | 0.872615 | False |
| alpha_upper_quartile_topup_1100 | 1.1 | -0.0106 | -234.4 | 0.0 | 6 | 7 | 0.920506 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0008 | 33.13 | 0.0 | 0.0 | 0.0 | 0.0 |
| old_thin | -0.005 | -72.11 | 0.001 | 0.0 | 0.0 | 0.00213 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move the alpha-score bucket field and risk policy into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
