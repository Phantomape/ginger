# exp-20260524-003 core_relative_strength_component_band_topup

## Hypothesis
The top-level alpha_score mostly saturates inside filled core trades, but the ranking surface's trend component may still separate the cleanest continuation entries. Already-qualified non-ETF/non-Commodity core signals with trend component at 1.0 may deserve a small cap-aware top-up without changing entries, exits, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_trend_component_perfect_topup
- changed_variable: trend_component_perfect_post_sizing_multiplier
- prior_trial_count: 3
- multiple_testing_risk_bucket: high
- new_evidence_type: new_production_visible_ranking_component_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8794
- EV delta: -0.0147
- PnL delta: 336.09
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| trend_component_perfect_topup_1025 | 1.025 | -0.0171 | 23.4 | 0.0016 | 15 | 13 | 0.915283 | False |
| trend_component_perfect_topup_1050 | 1.05 | -0.0147 | 336.09 | 0.0035 | 19 | 21 | 0.541132 | False |
| trend_component_perfect_topup_1075 | 1.075 | -0.0199 | 525.98 | 0.0051 | 19 | 24 | 0.375715 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| mid_weak | -0.0061 | 639.94 | 0.0035 | 0.0 | 0.0 | 0.017791 |
| old_thin | -0.0086 | -303.85 | 0.0036 | 0.0 | 0.0 | 0.007521 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move the trend component field and risk policy into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
