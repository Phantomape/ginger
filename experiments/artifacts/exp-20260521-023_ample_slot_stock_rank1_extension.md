# exp-20260521-023 ample_slot_stock_rank1_extension

## Hypothesis
The accepted ample-slot stock rank-1 1.05x top-up may be under-sized; if rank-1 stock signals are true replacement-value leaders when four or more slots are open, a modestly higher cap-aware scalar should improve EV across standard windows.

## Trial accounting
- trial_family: core_ample_slot_stock_rank1_topup_extension
- changed_variable: ample_slot_stock_rank1_risk_multiplier
- prior_trial_count: 3
- multiple_testing_risk_bucket: high
- new_evidence_type: not_declared

## Three-window aggregate
- baseline EV: 7.8941
- best EV: 7.8986
- EV delta: 0.0045
- EV delta pct: 0.00057
- PnL delta: 932.48
- decision: rejected

## Sweep summary
| variant | multiplier | EV delta | EV delta pct | PnL delta | DD delta | affected | windows | passed |
|---|---:|---:|---:|---:|---:|---:|---|---|
| rank1_1p0625x | 1.0625 | 0.0023 | 0.000291 | 323.63 | 0.0012 | 6 | late_strong | False |
| rank1_1p075x | 1.075 | 0.003 | 0.00038 | 308.68 | 0.0016 | 6 | late_strong | False |
| rank1_1p10x | 1.1 | 0.0045 | 0.00057 | 932.48 | 0.0039 | 7 | late_strong | False |

## Window deltas for selected variant
| window | EV | PnL | DD | survival |
|---|---:|---:|---:|---:|
| late_strong | 0.0062 | 133.56 | 0.0 | 0.0 |
| mid_weak | -0.0017 | 798.92 | 0.0039 | 0.0 |
| old_thin | 0.0 | 0.0 | 0.0 | 0.0 |

## Production impact
```text
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_required_if_candidate_passed": "Change AMPLE_SLOT_STOCK_RANK1_RISK_MULTIPLIER in quant/constants.py, which is consumed by the shared production_parity policy, then rerun this protocol.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Rejection reason / next evidence
Best variant failed Gate 4 because at least one standard window regressed on expected_value_score.

[
  "Do not retry nearby rank-1 ample-slot scalar values without new forward rows or a distinct production-visible feature.",
  "Prefer a different alpha family unless a new replacement-value cohort is identified."
]
