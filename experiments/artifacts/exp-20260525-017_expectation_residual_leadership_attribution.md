# exp-20260525-017 Expectation Residual Leadership Attribution

Decision: `observed_only_data_gap`.

Observed-only alpha search. No entries, exits, ranking, sizing, LLM/news, or orders changed.

## Coverage

```json
{
  "candidate_objects_total": 42,
  "candidate_source_breakdown": {
    "entry_execution_plan.deferred_breakout_signals": 7,
    "entry_execution_plan.slot_sliced_signals": 5,
    "pilot_entry_execution_plan.pilot_slot_sliced_signals": 6,
    "pilot_signals": 5,
    "signals": 19
  },
  "candidates_with_eps_estimate_delta_7d": 17,
  "closed_forward_outcomes": {
    "10d": 30,
    "20d": 30,
    "5d": 39
  },
  "expectation_join_status_counts": {
    "ledger_row_not_usable": 12,
    "missing_ledger_row": 2,
    "usable_ledger_missing_7d_delta": 11,
    "usable_ledger_with_7d_delta": 17
  },
  "ledger_joined_candidates": 40,
  "ledger_usable_candidates": 28,
  "positive_expectation_candidates": 7,
  "record_type_breakdown": {
    "deferred_breakout_signal": 7,
    "pilot_slot_sliced_signal": 6,
    "selected_pilot_signal": 5,
    "selected_signal": 19,
    "slot_sliced_signal": 5
  },
  "residual_context_ok_candidates": 29,
  "residual_context_status_counts": {
    "insufficient_residual_inputs": 13,
    "ok": 29
  },
  "residual_leader_candidates": 25
}
```

## Bucket Summary

| Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 7 | 5 | 1.4369% | 0 |  |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 18 | 17 | -4.7090% | 13 | -6.5487% |
| D_neither | 17 | 17 | 0.0331% | 17 | -1.7556% |

## Reconstructed Scout

Non-PIT reconstructed rows are shown only for research triage. They cannot pass the primary gate or promote live logic.

```json
{
  "bucket_a_closed_5d_outcomes": 5,
  "can_promote": false,
  "decision": "observed_only_data_gap",
  "not_gate4_evidence": true,
  "pit_caveat_counts": {
    "missing_next_earnings_date": 11,
    "no_prior_same_event_snapshot": 1
  },
  "positive_expectation_candidates": 7,
  "scope": "non_pit_reconstructed_scout_only",
  "source_quality_counts": {
    "missing": 2,
    "non_pit_reconstructed": 12,
    "pit_usable": 28
  },
  "total_usable_candidates": 39
}
```

| Scout Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 7 | 5 | 1.4369% | 0 |  |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 18 | 17 | -4.7090% | 13 | -6.5487% |
| D_neither | 17 | 17 | 0.0331% | 17 | -1.7556% |

## Gate

```json
{
  "bucket_a_closed_5d_outcomes": 5,
  "data_gap_reasons": [
    "bucket_a_closed_5d_outcomes"
  ],
  "decision": "observed_only_data_gap",
  "minimum_bucket_a_closed_5d_outcomes": 8,
  "minimum_total_usable_candidates": 30,
  "passed": false,
  "reason": "insufficient_bucket_or_total_sample",
  "total_usable_candidates": 39
}
```

No JavaScript was used.
