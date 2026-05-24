# exp-20260524-018 core_mid_alpha_mid_breadth_topup

## Hypothesis
Entry-day attribution shows the strongest surviving core profits are not only in raw high-alpha or raw high-breadth buckets. A mid alpha_score plus mid breadth_alignment interaction may identify non-overheated, sufficiently supported core entries that deserve a small cap-aware top-up without changing entries, exits, universe, news, or LLM logic.

## Trial accounting
- trial_family: core_mid_alpha_mid_breadth_interaction_topup
- changed_variable: mid_alpha_mid_breadth_post_sizing_multiplier
- prior_trial_count: 5
- multiple_testing_risk_bucket: high
- new_evidence_type: new_pit_component_interaction_readout

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8985
- EV delta: 0.0044
- PnL delta: 95.95
- decision: rejected_failed_gate4

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| mid_alpha_mid_breadth_topup_10125 | 1.0125 | 0.0031 | 70.7 | 0.0 | 2 | 2 | 1.0 | False |
| mid_alpha_mid_breadth_topup_1025 | 1.025 | 0.0044 | 95.95 | 0.0 | 2 | 2 | 1.0 | False |
| mid_alpha_mid_breadth_topup_1050 | 1.05 | 0.0044 | 95.95 | 0.0 | 2 | 2 | 1.0 | False |
| mid_alpha_mid_breadth_topup_1075 | 1.075 | 0.0044 | 95.95 | 0.0 | 2 | 2 | 1.0 | False |

## Selected Window Deltas
| window | EV | PnL | DD | survival | worst trade | tail loss share |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 0.0044 | 95.95 | 0.0 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move alpha_score, breadth_alignment component exposure, and the sizing policy into shared daily context/risk/portfolio modules with parity tests, then rerun the same three-window protocol before production use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout
Best variant failed adjusted-signal sample guard; the mid alpha/mid breadth interaction did not touch enough sized core signals.
