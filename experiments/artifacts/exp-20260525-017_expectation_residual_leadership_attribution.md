# exp-20260525-017 Expectation Residual Leadership Attribution

Decision: `observed_only_data_gap`.

Observed-only alpha search. No entries, exits, ranking, sizing, LLM/news, or orders changed.

## Coverage

```json
{
  "candidate_objects_total": 21,
  "candidate_source_breakdown": {
    "entry_execution_plan.deferred_breakout_signals": 4,
    "entry_execution_plan.slot_sliced_signals": 1,
    "pilot_signals": 4,
    "signals": 12
  },
  "candidates_with_eps_estimate_delta_7d": 1,
  "closed_forward_outcomes": {
    "10d": 20,
    "20d": 13,
    "5d": 20
  },
  "expectation_join_status_counts": {
    "ledger_row_not_usable": 1,
    "missing_ledger_row": 13,
    "usable_ledger_missing_7d_delta": 7
  },
  "ledger_joined_candidates": 8,
  "ledger_usable_candidates": 7,
  "positive_expectation_candidates": 0,
  "record_type_breakdown": {
    "deferred_breakout_signal": 4,
    "selected_pilot_signal": 4,
    "selected_signal": 12,
    "slot_sliced_signal": 1
  },
  "residual_context_ok_candidates": 8,
  "residual_context_status_counts": {
    "insufficient_residual_inputs": 13,
    "ok": 8
  },
  "residual_leader_candidates": 7
}
```

## Bucket Summary

| Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 0 | 0 |  | 0 |  |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 7 | 7 | -2.0788% | 7 | -6.7270% |
| D_neither | 14 | 13 | 1.2728% | 13 | -0.2747% |

## Gate

```json
{
  "bucket_a_closed_5d_outcomes": 0,
  "data_gap_reasons": [
    "bucket_a_closed_5d_outcomes",
    "total_usable_candidates"
  ],
  "decision": "observed_only_data_gap",
  "minimum_bucket_a_closed_5d_outcomes": 8,
  "minimum_total_usable_candidates": 30,
  "passed": false,
  "reason": "insufficient_bucket_or_total_sample",
  "total_usable_candidates": 20
}
```

No JavaScript was used.
