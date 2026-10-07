# exp-20260525-017 Expectation Residual Leadership Attribution

Decision: `rejected_expectation_residual_leadership_attribution`.

Observed-only alpha search. No entries, exits, ranking, sizing, LLM/news, or orders changed.

## Coverage

```json
{
  "candidate_objects_total": 54,
  "candidate_source_breakdown": {
    "entry_execution_plan.deferred_breakout_signals": 7,
    "entry_execution_plan.slot_sliced_signals": 5,
    "pilot_entry_execution_plan.pilot_slot_sliced_signals": 6,
    "pilot_signals": 8,
    "signals": 28
  },
  "candidates_with_eps_estimate_delta_7d": 24,
  "closed_forward_outcomes": {
    "10d": 50,
    "20d": 48,
    "5d": 51
  },
  "expectation_join_status_counts": {
    "ledger_row_not_usable": 16,
    "missing_ledger_row": 2,
    "usable_ledger_missing_7d_delta": 13,
    "usable_ledger_with_7d_delta": 23
  },
  "ledger_joined_candidates": 52,
  "ledger_usable_candidates": 36,
  "positive_expectation_candidates": 9,
  "record_type_breakdown": {
    "deferred_breakout_signal": 7,
    "pilot_slot_sliced_signal": 6,
    "selected_pilot_signal": 8,
    "selected_signal": 28,
    "slot_sliced_signal": 5
  },
  "residual_context_ok_candidates": 41,
  "residual_context_status_counts": {
    "insufficient_residual_inputs": 13,
    "ok": 41
  },
  "residual_leader_candidates": 36
}
```

## Bucket Summary

| Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 9 | 9 | -0.0131% | 9 | -0.0325% |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 27 | 24 | -3.6856% | 23 | -6.3570% |
| D_neither | 18 | 18 | -0.1158% | 18 | -1.2553% |

## Reconstructed Scout

Non-PIT reconstructed rows are shown only for research triage. They cannot pass the primary gate or promote live logic.

```json
{
  "bucket_a_closed_5d_outcomes": 9,
  "can_promote": false,
  "decision": "rejected_expectation_residual_leadership_attribution",
  "not_gate4_evidence": true,
  "pit_caveat_counts": {
    "missing_next_earnings_date": 12,
    "no_prior_same_event_snapshot": 3,
    "prior_snapshot_created_after_asof": 1
  },
  "positive_expectation_candidates": 9,
  "scope": "non_pit_reconstructed_scout_only",
  "source_quality_counts": {
    "missing": 2,
    "non_pit_reconstructed": 16,
    "pit_usable": 36
  },
  "total_usable_candidates": 51
}
```

| Scout Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |
|---|---:|---:|---:|---:|---:|
| A_positive_expectation_and_residual_leader | 9 | 9 | -0.0131% | 9 | -0.0325% |
| B_positive_expectation_only | 0 | 0 |  | 0 |  |
| C_residual_leader_only | 27 | 24 | -3.6856% | 23 | -6.3570% |
| D_neither | 18 | 18 | -0.1158% | 18 | -1.2553% |

## Gate

```json
{
  "bucket_a_closed_5d_outcomes": 9,
  "comparisons": [
    {
      "bucket_a_avg_return": -0.000131,
      "comparison_avg_return": null,
      "comparison_bucket": "B_positive_expectation_only",
      "horizon": "5d",
      "passed": false
    },
    {
      "bucket_a_avg_return": -0.000131,
      "comparison_avg_return": -0.036856,
      "comparison_bucket": "C_residual_leader_only",
      "horizon": "5d",
      "passed": true
    },
    {
      "bucket_a_avg_return": -0.000131,
      "comparison_avg_return": -0.001158,
      "comparison_bucket": "D_neither",
      "horizon": "5d",
      "passed": true
    },
    {
      "bucket_a_avg_return": -0.000325,
      "comparison_avg_return": null,
      "comparison_bucket": "B_positive_expectation_only",
      "horizon": "10d",
      "passed": false
    },
    {
      "bucket_a_avg_return": -0.000325,
      "comparison_avg_return": -0.06357,
      "comparison_bucket": "C_residual_leader_only",
      "horizon": "10d",
      "passed": true
    },
    {
      "bucket_a_avg_return": -0.000325,
      "comparison_avg_return": -0.012553,
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
  "total_usable_candidates": 51
}
```

No JavaScript was used.
