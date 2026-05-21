# exp-20260520-029 fact_tone_gap_bucket_v1

Decision: `observed_only_launch_recorded`.

## Hypothesis

SEC earnings attribution should separate factual improvement, tone packaging, and fact-tone divergence before testing another notional scalar.

## Trial Accounting

- mechanism_family: `sec_earnings_semantic_field`
- trial_family: `sec_fact_tone_gap_bucket`
- changed_variable: `fact_tone_gap_bucket`
- prior_trial_count: `33`
- multiple_testing_risk_bucket: `minimal`

## Current Evidence

```json
{
  "current_snapshot": {
    "asof_date": "2026-05-19",
    "candidate_count": 0,
    "closed_outcome_count": null,
    "closed_position_count": 0,
    "data_source": {
      "loaded_row_count": 0,
      "path": "D:\\Github\\ginger\\data\\non_ohlcv\\sec_filing_events_20260519.jsonl",
      "skipped_not_pit_safe_count": 0,
      "status": "loaded",
      "t1_evaluated_count": 0
    },
    "forward_paper_gate": null,
    "open_position_count": 0,
    "path": "data/paper_sleeves/sec_financial_report/snapshots.jsonl",
    "pending_count": 0,
    "primary_closed_outcome_count": null,
    "realized_inverse_pnl_to_date": null,
    "realized_no_trade_value_to_date": null,
    "realized_pnl_to_date": 0
  },
  "field_status": "implemented_in_shared_paper_sleeve_next_snapshot",
  "sample_fact_tone_gap_attribution": {
    "alters_orders": false,
    "alters_sizing": false,
    "default_off_attribution_only": true,
    "evidence_counts": {
      "guidance_cut_hits": 0,
      "guidance_raise_hits": 1,
      "negative_phrase_hits": 0,
      "positive_phrase_hits": 1
    },
    "evidence_span": [
      {
        "field": "positive_phrase_hits",
        "source": "sec_financial_report_t1_queue",
        "text": "revenue increased"
      },
      {
        "field": "guidance_raise_hits",
        "source": "sec_financial_report_t1_queue",
        "text": "raised outlook"
      }
    ],
    "fact_tone_gap_bucket": "fact_improvement_positive_tone",
    "language_bucket": "positive_language",
    "notes": "This field supports forward attribution only; it does not expand LLM authority or change paper/live orders.",
    "provenance": {
      "accession_number": "sample",
      "event_family": "earnings_8k",
      "form_base": "8-K",
      "ticker": "SAMPLE",
      "usable_trade_date": "2026-05-20"
    },
    "read_only": true,
    "rule_version": "sec_fact_tone_gap_bucket_v1",
    "schema_version": 1,
    "text_event_type": "earnings_release_text",
    "trade_enabled": false
  },
  "state_counts": {
    "closed": 0,
    "open": 0,
    "pending": 0
  }
}
```

## Next Evidence Needed

Collect forward returns, replacement value, and veto/allow attribution by fact_tone_gap_bucket.
