# exp-20260524-003 core_relative_strength_component_band_topup

## Hypothesis
The top-level alpha_score mostly saturates inside filled core trades, but its relative_strength component may still distinguish a moderate-strength sweet spot. Already-qualified non-ETF/non-Commodity core signals with relative_strength component between 0.50 and 0.65 may deserve a small cap-aware top-up without changing entries, exits, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_relative_strength_component_band_topup
- changed_variable: relative_strength_component_band_post_sizing_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_ranking_component_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8941
- EV delta: 0.0
- PnL delta: 0.0
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| rs_component_band_topup_1025 | 1.025 | 0.0 | 0.0 | 0.0 | 2 | 0 | 0.0 | False |
| rs_component_band_topup_1050 | 1.05 | -0.0002 | -3.98 | 0.0 | 4 | 2 | 0.0 | False |
| rs_component_band_topup_1075 | 1.075 | -0.0002 | -4.69 | 0.0 | 4 | 2 | 0.0 | False |
| rs_component_band_topup_1100 | 1.1 | -0.0002 | -8.67 | 0.0 | 4 | 2 | 0.0 | False |

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
  "promotion_required_if_accepted": "Move the relative-strength component field and risk policy into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed adjusted-signal sample guard; the relative-strength component band did not touch enough sized core signals.
