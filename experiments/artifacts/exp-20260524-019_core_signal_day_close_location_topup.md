# exp-20260524-019 core_signal_day_close_location_topup

## Hypothesis
Already-qualified core stock signals closing in the upper 25% of their signal-day range may reflect stronger end-of-day accumulation than the existing green-candle and SPY-relative flags alone. A small cap-aware risk top-up could improve expected_value_score without changing entry, exit, ranking, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_signal_day_close_location_risk
- changed_variable: high_signal_day_close_location_risk_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: moderate
- new_evidence_type: new_production_visible_entry_day_ohlcv_field

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8878
- EV delta: -0.0063
- PnL delta: 142.99
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| close_location_topup_10125 | 1.0125 | -0.0063 | 142.99 | 0.0004 | 6 | 4 | 0.515001 | False |
| close_location_topup_1025 | 1.025 | -0.0215 | 475.33 | 0.0016 | 10 | 16 | 0.540945 | False |
| close_location_topup_1050 | 1.05 | -0.0248 | 1274.76 | 0.0035 | 12 | 24 | 0.520914 | False |
| close_location_topup_1075 | 1.075 | -0.024 | 1838.78 | 0.0051 | 12 | 29 | 0.405976 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | -0.0082 | 73.64 | 0.0003 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0019 | 69.35 | 0.0004 | 0.0 | 0.0 | 0.0 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move signal_day_close_location feature, high-close-location state, and risk top-up into shared feature_layer/risk_engine/portfolio_engine with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed Gate 4 because at least one fixed window regressed in expected_value_score.
