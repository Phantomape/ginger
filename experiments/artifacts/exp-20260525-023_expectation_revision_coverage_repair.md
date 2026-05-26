# exp-20260525-023 Expectation Revision Coverage Repair

Decision: `observed_only_data_gap_explained`.

Read-only measurement repair. No entries, exits, ranking, sizing, LLM/news, or orders changed.

## Repair Gate

```json
{
  "all_missing_reasons_explained": true,
  "decision": "observed_only_data_gap_explained",
  "passed": true,
  "strategy_behavior_changed": false,
  "unknown_reason_count": 0
}
```

## Alpha Readiness

```json
{
  "blocking_reasons": [
    "positive_expectation_candidates_zero"
  ],
  "decision": "expectation_coverage_still_empty",
  "note": "A positive expectation candidate is not sufficient for alpha interpretation; exp-20260525-021 must still pass Bucket A and total coverage gates before exp-20260525-017 is interpreted.",
  "ready_to_rerun_attribution": false,
  "ready_to_rerun_readiness_audit": false,
  "rerun_attribution_command": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260525_017_expectation_residual_leadership_attribution.py",
  "rerun_readiness_command": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260525_021_expectation_residual_readiness_audit.py"
}
```

## Coverage Summary

```json
{
  "candidate_objects_total": 21,
  "delta_availability": {
    "eps_estimate_delta_30d_available": 0,
    "eps_estimate_delta_30d_gap_counts": {
      "missing_ledger_row": 13,
      "same_event_history_too_short_for_30d_delta": 8
    },
    "eps_estimate_delta_7d_available": 1,
    "eps_estimate_delta_7d_gap_counts": {
      "missing_ledger_row": 13,
      "same_event_history_too_short_for_7d_delta": 7
    }
  },
  "expectation_state_counts": {
    "missing_ledger_row": 13,
    "non_positive_eps_estimate_delta_7d": 1,
    "usable_ledger_missing_7d_delta": 7
  },
  "ledger_join_coverage": {
    "ledger_root_cause_counts": {
      "missing_ledger_file_and_same_day_earnings_snapshot": 2,
      "missing_ledger_file_snapshot_exists": 11
    },
    "ledger_rows_joined": 8,
    "missing_ledger_rows": 13,
    "pit_caveat_counts": {},
    "usable_ledger_rows": 8
  },
  "positive_expectation_candidates": 0
}
```

No JavaScript was used.
