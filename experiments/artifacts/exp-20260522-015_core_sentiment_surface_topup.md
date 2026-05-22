# exp-20260522-015 core_sentiment_surface_topup

## Hypothesis
Core stock signals in constructive non-theme sentiment surfaces may deserve a small cap-aware risk top-up because broad trend quality should matter more than single-name path shape. The rule should improve EV without changing entry filters, ranking, exits, universe, LLM, or news logic.

## Trial accounting
- trial_family: core_sentiment_surface_constructive_risk
- changed_variable: sentiment_surface_constructive_risk_multiplier
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
| constructive_sentiment_topup_1025 | 1.025 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| constructive_sentiment_topup_1050 | 1.05 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| constructive_sentiment_topup_1075 | 1.075 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |
| constructive_sentiment_topup_1100 | 1.1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0.0 | False |

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
  "promotion_required_if_accepted": "Move sentiment-surface constructive state and risk top-up into shared sentiment_surface/portfolio_engine plumbing with tests, then rerun the same three-window protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed adjusted-signal sample guard.
