# exp-20260520-030 no_trade_alpha_report_v1

Decision: `observed_only_launch_recorded`.

## Hypothesis

Core-misfit alpha should first prove avoided long-loss value on closed 10d paper outcomes rather than jumping to live shorts.

## Trial Accounting

- mechanism_family: `core_misfit_no_trade`
- trial_family: `core_misfit_no_trade_forward_maturation`
- changed_variable: `core_misfit_no_trade_alpha_report`
- prior_trial_count: `3`
- multiple_testing_risk_bucket: `minimal`

## Current Evidence

```json
{
  "current_snapshot": {
    "asof_date": "2026-05-19",
    "candidate_count": 0,
    "closed_outcome_count": 0,
    "closed_position_count": null,
    "data_source": {
      "source": "current_core_signals_and_entry_execution_plan",
      "status": "loaded"
    },
    "forward_paper_gate": {
      "checks": {
        "max_single_ticker_inverse_positive_share": false,
        "min_closed_primary_outcomes": false,
        "positive_inverse_pnl": false,
        "positive_no_trade_value": false
      },
      "metrics": {
        "closed_primary_outcomes": 0,
        "inverse_short_pnl": 0,
        "inverse_short_win_rate": null,
        "max_single_ticker_inverse_positive_share": null,
        "no_trade_avoided_value": 0
      },
      "passed": false,
      "reasons": [
        "min_closed_primary_outcomes",
        "positive_no_trade_value",
        "positive_inverse_pnl",
        "max_single_ticker_inverse_positive_share"
      ],
      "status": "blocked",
      "trade_enabled_after_gate": false
    },
    "open_position_count": 0,
    "path": "data/paper_sleeves/core_misfit/snapshots.jsonl",
    "pending_count": 0,
    "primary_closed_outcome_count": 0,
    "realized_inverse_pnl_to_date": 0,
    "realized_no_trade_value_to_date": 0,
    "realized_pnl_to_date": null
  },
  "no_trade_alpha_report": {
    "alters_orders": false,
    "closed_outcomes_remaining_before_gate_test": 20,
    "min_closed_primary_outcomes": 20,
    "next_allowed_action": "observed_only_until_min_closed_10d_outcomes",
    "notes": "Live short or exclusion tests stay blocked until the closed 10d no-trade avoided-value sample reaches the configured gate.",
    "primary_closed_outcome_count": 0,
    "primary_horizon_days": 10,
    "read_only": true,
    "realized_inverse_short_pnl": 0,
    "realized_no_trade_avoided_value": 0,
    "rule_version": "core_misfit_no_trade_alpha_report_v1",
    "schema_version": 1,
    "trade_enabled": false,
    "unrealized_inverse_short_pnl": 0,
    "unrealized_no_trade_avoided_value": 0
  }
}
```

## Next Evidence Needed

Reach at least 20 closed 10d outcomes with positive no-trade avoided value before any exclusion or live-path haircut test.
