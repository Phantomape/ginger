# exp-20260521-020 ample_slot_stock_rank2_topup

## Hypothesis
On days with at least four available slots, the second planned non-ETF/non-commodity stock candidate may be a replacement-value signal that deserves a small cap-aware post-sizing top-up.

## Trial accounting
- trial_family: core_slot_rank_post_sizing_topup
- changed_variable: ample_slot_stock_rank2_risk_multiplier
- prior_trial_count: 3
- multiple_testing_risk_bucket: high
- new_evidence_type: new_replacement_value_cohort

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8941
- EV delta: 0.0
- PnL delta: 0.0
- decision: rejected

## Sweep summary
| variant | multiplier | EV delta | PnL delta | DD delta | affected | windows | passed |
|---|---:|---:|---:|---:|---:|---|---|
| rank2_1p025x | 1.025 | 0.0 | 0.0 | 0.0 | 0 |  | False |
| rank2_1p05x | 1.05 | 0.0 | 0.0 | 0.0 | 0 |  | False |
| rank2_1p075x | 1.075 | 0.0 | 0.0 | 0.0 | 0 |  | False |
| rank2_1p10x | 1.1 | 0.0 | 0.0 | 0.0 | 0 |  | False |

## Window deltas for selected variant
| window | EV | PnL | DD | survival |
|---|---:|---:|---:|---:|
| late_strong | 0.0 | 0.0 | 0.0 | 0.0 |
| mid_weak | 0.0 | 0.0 | 0.0 | 0.0 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```text
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_accepted": "Move rank-2 top-up into quant/production_parity.py and add shared policy tests before any production orders change.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Rejection reason / next evidence
Best variant failed sample guard; affected rank-2 top-up signals are too sparse.

[
  "Do not retry nearby rank-2 scalar values without new forward rows or a new production-visible replacement-value feature.",
  "If a variant passes, promote into shared production_parity policy and rerun this same three-window protocol."
]
