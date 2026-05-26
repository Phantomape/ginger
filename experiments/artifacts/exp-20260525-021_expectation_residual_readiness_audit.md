# exp-20260525-021 Expectation Residual Readiness Audit

Decision: `observed_only_data_gap`.

Read-only measurement repair. No entries, exits, ranking, sizing, LLM/news, or orders changed.

## Readiness Gate

```json
{
  "bucket_a_closed_5d_outcomes": 0,
  "data_gap_reasons": [
    "bucket_a_closed_5d_outcomes",
    "total_usable_candidates"
  ],
  "decision": "observed_only_data_gap",
  "exact_rerun_command": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260525_017_expectation_residual_leadership_attribution.py",
  "interpretation_rule": "Only rerun and interpret exp-20260525-017 when this readiness gate passes.",
  "minimum_bucket_a_closed_5d_outcomes": 8,
  "minimum_total_usable_candidates": 30,
  "passed": false,
  "ready_to_rerun_attribution": false,
  "reason": "insufficient_bucket_or_total_sample",
  "total_usable_candidates": 20
}
```

## Coverage

```json
{
  "bucket_a_readiness_blocking_reason_counts": {
    "expectation:ledger_row_not_usable": 1,
    "expectation:missing_eps_estimate_delta_7d": 7,
    "expectation:missing_ledger_row": 13,
    "forward_5d:missing_5d_forward_price": 1,
    "residual:insufficient_residual_inputs": 13,
    "residual:not_residual_leader_neutral": 1
  },
  "bucket_counts": {
    "A_positive_expectation_and_residual_leader": 0,
    "B_positive_expectation_only": 0,
    "C_residual_leader_only": 7,
    "D_neither": 14
  },
  "candidate_objects_total": 21,
  "estimate_revision_delta_availability": {
    "eps_estimate_delta_30d_available": 0,
    "eps_estimate_delta_7d_available": 1
  },
  "estimate_revision_ledger_join_coverage": {
    "expectation_join_status_counts": {
      "ledger_row_not_usable": 1,
      "missing_ledger_row": 13,
      "usable_ledger_missing_7d_delta": 7
    },
    "ledger_joined_candidates": 8,
    "ledger_usable_candidates": 7,
    "positive_expectation_candidates": 0
  },
  "forward_close_availability": {
    "10d": {
      "closed": 20,
      "gap_reason_counts": {
        "missing_10d_forward_price": 1
      },
      "missing": 1
    },
    "20d": {
      "closed": 13,
      "gap_reason_counts": {
        "missing_20d_forward_price": 8
      },
      "missing": 8
    },
    "5d": {
      "closed": 20,
      "gap_reason_counts": {
        "missing_5d_forward_price": 1
      },
      "missing": 1
    }
  },
  "residual_context_coverage": {
    "residual_context_ok_candidates": 8,
    "residual_context_status_counts": {
      "insufficient_residual_inputs": 13,
      "ok": 8
    },
    "residual_leader_candidates": 7,
    "residual_leader_states": [
      "residual_leader",
      "strong_residual_leader"
    ]
  }
}
```

## Rerun Command

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260525_017_expectation_residual_leadership_attribution.py
```

No JavaScript was used.
