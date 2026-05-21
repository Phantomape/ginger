# exp-20260520-027 replacement_value_report_v1

Decision: `observed_only_launch_recorded`.

## Hypothesis

Broad-market leadership should mature as a daily paper ledger with closed/open/pending replacement value before any core expansion.

## Trial Accounting

- mechanism_family: `broad_market_forward_maturation`
- trial_family: `broad_market_forward_maturation`
- changed_variable: `broad_market_replacement_value_report`
- prior_trial_count: `15`
- multiple_testing_risk_bucket: `low`

## Current Evidence

```json
{
  "current_snapshot": {
    "asof_date": "2026-05-19",
    "candidate_count": 0,
    "closed_outcome_count": null,
    "closed_position_count": 0,
    "data_source": {
      "path": "D:\\Github\\ginger\\data\\state\\broad_market_paper\\universe.json",
      "status": "missing",
      "ticker_count": 0
    },
    "forward_paper_gate": {
      "checks": {
        "max_single_ticker_positive_share": false,
        "max_top5_positive_share": false,
        "min_closed_trades": false,
        "min_win_rate": false,
        "positive_net_pnl": false
      },
      "metrics": {
        "closed_trades": 0,
        "realized_pnl": 0,
        "single_ticker_positive_share": null,
        "top5_positive_share": null,
        "win_rate": null
      },
      "passed": false,
      "reasons": [
        "min_closed_trades",
        "positive_net_pnl",
        "min_win_rate",
        "max_single_ticker_positive_share",
        "max_top5_positive_share"
      ],
      "status": "blocked",
      "trade_enabled_after_gate": false
    },
    "open_position_count": 0,
    "path": "data/paper_sleeves/broad_market/snapshots.jsonl",
    "pending_count": 0,
    "primary_closed_outcome_count": null,
    "realized_inverse_pnl_to_date": null,
    "realized_no_trade_value_to_date": null,
    "realized_pnl_to_date": 0
  },
  "field_status": "implemented_in_shared_paper_sleeve_next_snapshot",
  "replacement_value_report": {
    "alters_orders": false,
    "by_ticker": {},
    "candidate_count": 0,
    "closed_count": 0,
    "closed_pnl": 0,
    "displaced_resource_default": "paper_cash_slot",
    "forward_outcome_horizon_days": 20,
    "open_count": 0,
    "open_unrealized_pnl": 0,
    "pending_count": 0,
    "positive_closed_pnl": 0,
    "promotion_blockers": [
      "needs_closed_forward_outcomes",
      "needs_replacement_value_vs_core_or_cash"
    ],
    "read_only": true,
    "rule_version": "broad_market_forward_replacement_value_v1",
    "schema_version": 1,
    "skipped_count": 0,
    "top_ticker_positive_pnl_share": null,
    "trade_enabled": false
  }
}
```

## Next Evidence Needed

Populate the candidate universe feed, then collect closed 20d replacement-value outcomes versus paper cash or displaced core slots.
