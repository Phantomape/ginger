# exp-20260522-017 core_pullback_in_uptrend_topup

## Hypothesis
Core stock signals that remain in a 20d uptrend but have stalled or pulled back over the last 5d may offer better follow-through than straight continuation entries. A small cap-aware risk top-up should improve EV without changing entry filters, ranking, exits, universe, LLM, or news logic.

## Trial accounting
- trial_family: core_reversal_vs_continuation_state_risk
- changed_variable: pullback_in_uptrend_risk_multiplier
- prior_trial_count: 0
- multiple_testing_risk_bucket: low
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
| pullback_uptrend_topup_1025 | 1.025 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| pullback_uptrend_topup_1050 | 1.05 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| pullback_uptrend_topup_1075 | 1.075 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| pullback_uptrend_topup_1100 | 1.1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |

## Selected window deltas
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
  "promotion_required_if_accepted": "Move reversal_vs_continuation_state feature and pullback state-aware risk top-up into shared feature_layer/risk_engine/portfolio_engine plumbing with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed adjusted-signal sample guard.
