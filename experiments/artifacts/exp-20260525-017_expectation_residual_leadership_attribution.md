# exp-20260525-017 Expectation Residual Leadership Attribution

Decision: `rejected_expectation_residual_leadership_attribution`.

Observed-only alpha search. No entries, exits, ranking, sizing, LLM/news, or orders changed.

## Coverage

```json
{
  "candidate_objects_total": 48,
  "candidate_source_breakdown": {
    "entry_execution_plan.deferred_breakout_signals": 7,
    "entry_execution_plan.slot_sliced_signals": 5,
    "pilot_entry_execution_plan.pilot_slot_sliced_signals": 6,
    "pilot_signals": 6,
    "signals": 24
  },
  "candidates_with_eps_estimate_delta_7d": 19,
  "closed_forward_outcomes": {
    "10d": 45,
    "20d": 45,
    "5d": 48
  },
  "expectation_join_status_counts": {
    "ledger_row_not_usable": 14,
    "missing_ledger_row": 2,
    "usable_ledger_missing_7d_delta": 13,
    "usable_ledger_with_7d_delta": 19
  },
  "ledger_joined_candidates": 46,
  "ledger_usable_candidates": 32,
  "positive_expectation_candidates": 8,
  "record_type_breakdown": {
    "deferred_breakout_signal": 7,
    "pilot_slot_sliced_signal": 6,
    "selected_pilot_signal": 6,
    "selected_signal": 24,
    "slot_sliced_signal": 5
  },
  "residual_context_ok_candidates": 35,
  "residual_context_status_counts": {
    "insufficient_residual_inputs": 13,
    "ok": 35
  },
  "residual_leader_candidates": 30
}
```

## Bucket Summary

| Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 8 | 8 | 1.1268% | 8 | 1.3937% |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 22 | 22 | -3.6835% | 20 | -7.5413% |
| D_neither | 18 | 18 | -0.1158% | 17 | -1.7556% |

## Reconstructed Scout

Non-PIT reconstructed rows are shown only for research triage. They cannot pass the primary gate or promote live logic.

```json
{
  "bucket_a_closed_5d_outcomes": 8,
  "can_promote": false,
  "decision": "rejected_expectation_residual_leadership_attribution",
  "not_gate4_evidence": true,
  "pit_caveat_counts": {
    "missing_next_earnings_date": 12,
    "no_prior_same_event_snapshot": 2
  },
  "positive_expectation_candidates": 8,
  "scope": "non_pit_reconstructed_scout_only",
  "source_quality_counts": {
    "missing": 2,
    "non_pit_reconstructed": 14,
    "pit_usable": 32
  },
  "total_usable_candidates": 48
}
```

| Scout Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 8 | 8 | 1.1268% | 8 | 1.3937% |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 22 | 22 | -3.6835% | 20 | -7.5413% |
| D_neither | 18 | 18 | -0.1158% | 17 | -1.7556% |

## Gate

```json
{
  "bucket_a_closed_5d_outcomes": 8,
  "comparisons": [
    {
      "bucket_a_avg_return": 0.011268,
      "comparison_avg_return": null,
      "comparison_bucket": "B_positive_expectation_only",
      "horizon": "5d",
      "passed": false
    },
    {
      "bucket_a_avg_return": 0.011268,
      "comparison_avg_return": -0.036835,
      "comparison_bucket": "C_residual_leader_only",
      "horizon": "5d",
      "passed": true
    },
    {
      "bucket_a_avg_return": 0.011268,
      "comparison_avg_return": -0.001158,
      "comparison_bucket": "D_neither",
      "horizon": "5d",
      "passed": true
    },
    {
      "bucket_a_avg_return": 0.013937,
      "comparison_avg_return": null,
      "comparison_bucket": "B_positive_expectation_only",
      "horizon": "10d",
      "passed": false
    },
    {
      "bucket_a_avg_return": 0.013937,
      "comparison_avg_return": -0.075413,
      "comparison_bucket": "C_residual_leader_only",
      "horizon": "10d",
      "passed": true
    },
    {
      "bucket_a_avg_return": 0.013937,
      "comparison_avg_return": -0.017556,
      "comparison_bucket": "D_neither",
      "horizon": "10d",
      "passed": true
    }
  ],
  "concentration": {
    "max_single_ticker_positive_guardrail": 0.5,
    "max_single_ticker_positive_share": 0.603954,
    "passed": false,
    "top5_positive_contribution_guardrail": 0.6,
    "top5_positive_contribution_share": 1.0
  },
  "decision": "rejected_expectation_residual_leadership_attribution",
  "passed": false,
  "reason": "bucket_a_failed_outperformance_or_concentration",
  "total_usable_candidates": 48
}
```

No JavaScript was used.
