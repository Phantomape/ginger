# exp-20260525-017 Expectation Residual Leadership Attribution

Decision: `observed_only_data_gap`.

Observed-only alpha search. No entries, exits, ranking, sizing, LLM/news, or orders changed.

## Coverage

```json
{
  "candidate_objects_total": 29,
  "candidate_source_breakdown": {
    "entry_execution_plan.deferred_breakout_signals": 7,
    "entry_execution_plan.slot_sliced_signals": 5,
    "pilot_signals": 4,
    "signals": 13
  },
  "candidates_with_eps_estimate_delta_7d": 5,
  "closed_forward_outcomes": {
    "10d": 21,
    "20d": 20,
    "5d": 21
  },
  "expectation_join_status_counts": {
    "ledger_row_not_usable": 12,
    "missing_ledger_row": 2,
    "usable_ledger_missing_7d_delta": 10,
    "usable_ledger_with_7d_delta": 5
  },
  "ledger_joined_candidates": 27,
  "ledger_usable_candidates": 15,
  "positive_expectation_candidates": 0,
  "record_type_breakdown": {
    "deferred_breakout_signal": 7,
    "selected_pilot_signal": 4,
    "selected_signal": 13,
    "slot_sliced_signal": 5
  },
  "residual_context_ok_candidates": 16,
  "residual_context_status_counts": {
    "insufficient_residual_inputs": 13,
    "ok": 16
  },
  "residual_leader_candidates": 12
}
```

## Bucket Summary

| Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 0 | 0 |  | 0 |  |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 12 | 7 | -2.0788% | 7 | -6.7270% |
| D_neither | 17 | 14 | 1.2881% | 14 | 0.0609% |

## Reconstructed Scout

Non-PIT reconstructed rows are shown only for research triage. They cannot pass the primary gate or promote live logic.

```json
{
  "bucket_a_closed_5d_outcomes": 0,
  "can_promote": false,
  "decision": "observed_only_data_gap",
  "not_gate4_evidence": true,
  "pit_caveat_counts": {
    "missing_next_earnings_date": 11,
    "no_prior_same_event_snapshot": 1
  },
  "positive_expectation_candidates": 0,
  "scope": "non_pit_reconstructed_scout_only",
  "source_quality_counts": {
    "missing": 2,
    "non_pit_reconstructed": 12,
    "pit_usable": 15
  },
  "total_usable_candidates": 21
}
```

| Scout Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 0 | 0 |  | 0 |  |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 12 | 7 | -2.0788% | 7 | -6.7270% |
| D_neither | 17 | 14 | 1.2881% | 14 | 0.0609% |

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
  "total_usable_candidates": 21
}
```

No JavaScript was used.
