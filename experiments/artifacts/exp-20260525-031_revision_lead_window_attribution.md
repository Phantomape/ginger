# exp-20260525-031 Revision Lead Window Attribution

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
  "closed_forward_outcomes": {
    "10d": 20,
    "20d": 13,
    "5d": 20
  },
  "positive_revision_lead_candidates": 1,
  "positive_revision_lead_unique_tickers": [
    "COHR"
  ],
  "record_type_breakdown": {
    "deferred_breakout_signal": 4,
    "selected_pilot_signal": 4,
    "selected_signal": 12,
    "slot_sliced_signal": 1
  },
  "revision_index": {
    "ledger_rows_total": 2017,
    "positive_revision_rows": 22,
    "positive_revision_rows_missing_effective_trade_date": 0,
    "positive_revision_rows_with_effective_trade_date": 22,
    "positive_revision_unique_tickers": [
      "AAPL",
      "AMD",
      "APP",
      "CAT",
      "COHR",
      "COIN",
      "CVX",
      "DDOG",
      "DIS",
      "LLY",
      "MTSI",
      "MU",
      "NVDA",
      "NVO",
      "SOFI",
      "SPOT",
      "V",
      "XOM"
    ],
    "revision_status_counts": {
      "ledger_row_not_usable": 1419,
      "non_positive_delta_prev": 576,
      "positive_delta_prev": 22
    }
  },
  "revision_lead_status_counts": {
    "matched_positive_revision_lead": 1,
    "no_positive_revision_in_lead_window": 20
  },
  "same_day_revision_status_counts": {
    "ledger_row_not_usable": 11,
    "missing_ledger_row": 2,
    "non_positive_delta_prev": 8
  }
}
```

## Current Positions

```json
{
  "current_position_count": 11,
  "entry_lead_match_count": 1,
  "entry_lead_matches": [
    {
      "avg_cost": 383.009,
      "candidate_effective_trade_date": "2026-05-11",
      "entry_date": "2026-05-11",
      "eps_estimate": 1.61,
      "eps_estimate_delta_prev": 0.06,
      "matched": true,
      "next_earnings_date": "2026-08-12",
      "opened_by_strategy": "pilot_breakout_long",
      "pit_caveat": null,
      "position_source": "positions",
      "revision_as_of_date": "2026-05-09",
      "revision_direction_prev": "up",
      "revision_effective_trade_date": "2026-05-11",
      "revision_lead_calendar_days": 2,
      "revision_lead_status": "matched_positive_revision_lead",
      "revision_lead_trading_days": 0,
      "same_event_history_count": 1,
      "shares": 16,
      "source_snapshot_path": "data/earnings_snapshot_20260509.json",
      "source_snapshot_pit_safe": true,
      "ticker": "COHR"
    }
  ],
  "ticker_overlap_count": 4,
  "ticker_overlap_with_any_positive_revision": [
    "AMD",
    "APP",
    "COHR",
    "NVDA"
  ]
}
```

## Bucket Summary

| Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_positive_eps_revision_lead_0_3td | 1 | 1 | 0.7269% | 1 | -0.4451% | 0 |  |
| D_no_positive_eps_revision_lead_0_3td | 20 | 19 | 0.0667% | 19 | -2.6429% | 13 | 3.4283% |

## Gate

```json
{
  "bucket_a_closed_5d_outcomes": 1,
  "data_gap_reasons": [
    "bucket_a_closed_5d_outcomes"
  ],
  "decision": "observed_only_data_gap",
  "minimum_bucket_a_closed_5d_outcomes": 4,
  "minimum_total_closed_5d_outcomes": 20,
  "passed": false,
  "reason": "insufficient_positive_revision_lead_sample",
  "total_closed_5d_outcomes": 20
}
```

No JavaScript was used.
