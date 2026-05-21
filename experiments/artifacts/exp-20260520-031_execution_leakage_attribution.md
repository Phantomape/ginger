# exp-20260520-031 entry_execution_attribution_v1

Decision: `observed_only_launch_recorded`.

## Hypothesis

Execution alpha should quantify planned next-open fills, gap erosion, cancel reasons, and missing live delay telemetry before testing a shared execution policy variable.

## Trial Accounting

- mechanism_family: `execution_slippage_leakage`
- trial_family: `execution_leakage_report`
- changed_variable: `execution_leakage_report`
- prior_trial_count: `10`
- multiple_testing_risk_bucket: `minimal`

## Current Evidence

```json
{
  "entry_execution_attribution": {
    "adverse_gap_down_cancel_count": 1,
    "candidate_events": 52,
    "entered_count": 22,
    "gap_cancel_count": 5,
    "reason_counts": {
      "adverse_gap_down_cancel": 1,
      "entered": 22,
      "gap_cancel": 5,
      "no_shares": 9,
      "scarce_slot_breakout_deferred": 6,
      "slot_sliced": 9
    },
    "sample_skips": [
      {
        "available_slots_at_entry_loop": 3,
        "candidate_rank": 3,
        "date": "2024-10-18",
        "decision": "gap_cancel",
        "details": {
          "adverse_gap_cancel_pct": 0.02,
          "cancel_gap_pct": 0.015,
          "fill_date": "2024-10-21",
          "fill_price": 31.13,
          "signal_entry": 30.64
        },
        "strategy": "breakout_long",
        "ticker": "SLV"
      },
      {
        "available_slots_at_entry_loop": 1,
        "candidate_rank": null,
        "date": "2024-10-21",
        "decision": "scarce_slot_breakout_deferred",
        "details": {
          "active_positions": 4,
          "defer_breakout_max_min_index_pct_from_ma": null,
          "defer_breakout_slots_lte": 1,
          "min_index_pct_from_ma": null
        },
        "strategy": "breakout_long",
        "ticker": "APP"
      },
      {
        "available_slots_at_entry_loop": 1,
        "candidate_rank": 1,
        "date": "2024-10-29",
        "decision": "no_shares",
        "details": {
          "has_sizing": true,
          "risk_multipliers": {
            "tqs_risk_multiplier_applied": 0.25,
            "trend_mid_sector_dispersion_risk_multiplier_applied": 1.25,
            "trend_tech_tight_gap_risk_multiplier_applied": 0.0
          },
          "risk_pct_after": null,
          "risk_pct_before": null,
          "shares_to_buy": 0
        },
        "strategy": "trend_long",
        "ticker": "GOOG"
      },
      {
        "available_slots_at_entry_loop": 1,
        "candidate_rank": 1,
        "date": "2024-10-30",
        "decision": "gap_cancel",
        "details": {
          "adverse_gap_cancel_pct": 0.02,
          "cancel_gap_pct": 0.015,
          "fill_date": "2024-10-31",
          "fill_price": 187.2252,
          "signal_entry": 176.54
        },
        "strategy": "trend_long",
        "ticker": "BKNG"
      },
      {
        "available_slots_at_entry_loop": 1,
        "candidate_rank": null,
        "date": "2024-10-30",
        "decision": "scarce_slot_breakout_deferred",
        "details": {
          "active_positions": 4,
          "defer_breakout_max_min_index_pct_from_ma": null,
          "defer_breakout_slots_lte": 1,
          "min_index_pct_from_ma": null
        },
        "strategy": "breakout_long",
        "ticker": "GOOG"
      }
    ],
    "skip_rate": 0.5769,
    "skipped_count": 30
  },
  "manual_delay_source_available": false,
  "next_required_field": "live_order_decision_timestamp_vs_planned_next_open",
  "source_backtest": "data/backtests/backtest_results_20260520.json"
}
```

## Next Evidence Needed

Add live planned-vs-actual timestamp and fill telemetry; only then test one shared execution policy variable such as net R:R invalidation.
