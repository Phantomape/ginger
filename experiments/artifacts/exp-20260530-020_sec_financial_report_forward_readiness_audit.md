# exp-20260530-020 SEC Financial-Report Forward Readiness Audit

Decision: `rejected_no_forward_sec_financial_report_sample`.

This was an alpha-search readiness audit, not a strategy change.

## Canonical Baseline

| Window | EV | PnL | Trades | Survival |
|---|---:|---:|---:|---:|
| late_strong | 5.1628 | $117,072.92 | 18 | 0.8039 |
| mid_weak | 2.1402 | $78,110.11 | 21 | 0.7925 |
| old_thin | 0.5911 | $39,667.96 | 22 | 0.8667 |

The before/after canonical core metrics are unchanged because this run is read-only.

## Forward Snapshot Rollup

- snapshot rows: `25`
- unique as-of dates: `19`
- date range: `2026-05-10` to `2026-05-29`
- loaded SEC event rows: `459`
- T+1 evaluated rows: `31`
- candidate count: `0`
- filled count: `0`
- closed outcomes: `0`
- realized paper PnL: `$0.00`

## Gate 2

```json
{
  "llm_dependency": "none",
  "missing_required_fields": [],
  "operator_open_positions_check": {
    "checked_groups": [
      "positions",
      "observations"
    ],
    "checked_rows": 13,
    "file": "operator_inputs\\open_positions.json",
    "missing_required_fields": [],
    "passed": true
  },
  "passed": true,
  "required_runtime_fields": [
    "operator_inputs/open_positions.json.positions[].entry_date",
    "operator_inputs/open_positions.json.positions[].target_price",
    "snapshot.asof_date",
    "snapshot.candidate_count",
    "snapshot.pending_count",
    "snapshot.open_position_count",
    "snapshot.closed_position_count",
    "snapshot.realized_pnl_to_date",
    "state.pending_entries",
    "state.open_positions",
    "state.closed_positions"
  ]
}
```

## Gate 4

```json
{
  "candidate_count_min": 10,
  "candidate_count_sum": 0,
  "candidate_date_count": 0,
  "candidate_date_count_min": 5,
  "closed_position_count": 0,
  "closed_position_count_min": 10,
  "failed_reasons": [
    "no_or_too_few_forward_candidates",
    "candidate_date_coverage_too_small",
    "no_or_too_few_closed_forward_outcomes",
    "no_positive_forward_realized_pnl"
  ],
  "latest_realized_pnl_to_date": 0.0,
  "minimum_core_survival_rate": 0.7925,
  "passed": false,
  "promotion_grade": false
}
```

## Production Impact

No shared policy, run adapter, backtester adapter, production watchlist, order path, ranking, sizing, exits, LLM, or news behavior changed.

No JavaScript was used.
