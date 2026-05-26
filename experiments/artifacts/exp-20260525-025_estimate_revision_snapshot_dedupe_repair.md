# exp-20260525-025 Estimate Revision Snapshot Dedupe Repair

Decision: `accepted_measurement_repair_duplicate_snapshot_guard`.

Measurement repair only. No entries, exits, ranking, sizing, LLM/news, or orders changed.

## Repair Gate

```json
{
  "candidate_rows_changed": 1,
  "decision": "accepted_measurement_repair_duplicate_snapshot_guard",
  "duplicate_dates_with_selection_change": 4,
  "duplicate_snapshot_dates": 4,
  "passed": true,
  "strategy_behavior_changed": false
}
```

## Candidate Impact

```json
{
  "candidate_objects_total": 21,
  "candidate_rows_changed": 1,
  "legacy_pit_caveat_counts": {
    "current_snapshot_created_after_asof": 1,
    "missing_next_earnings_date": 11,
    "missing_row": 2,
    "none": 7
  },
  "legacy_positive_expectation_candidates": 0,
  "legacy_usable_candidates": 7,
  "repaired_pit_caveat_counts": {
    "missing_next_earnings_date": 11,
    "missing_row": 2,
    "none": 8
  },
  "repaired_positive_expectation_candidates": 0,
  "repaired_usable_candidates": 8
}
```

## Alpha Readiness

```json
{
  "blocking_reasons": [
    "positive_expectation_candidates_zero"
  ],
  "decision": "expectation_positive_candidates_still_zero_after_dedupe",
  "note": "This code repair fixes duplicate snapshot selection only. Any canonical ledger files generated before the helper repair should be rebuilt or verified before exp-20260525-021 or exp-20260525-017 consumes the repaired rows.",
  "ready_to_rerun_attribution": false,
  "ready_to_rerun_readiness_audit": false
}
```

No JavaScript was used.
