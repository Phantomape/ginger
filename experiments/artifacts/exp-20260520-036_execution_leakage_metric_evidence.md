# exp-20260520-036 latest_entry_execution_attribution_v1

Decision: `attribution_only_backtest_evidence_collected`.

## Hypothesis

Execution alpha should first measure planned entry skips, gap cancels, slot slicing, and no-share decisions before testing a shared execution rule.

## Trial Accounting

- mechanism_family: `execution_slippage_leakage`
- trial_family: `execution_leakage_report`
- changed_variable: `entry_execution_attribution`
- prior_trial_count: `10`
- multiple_testing_risk_bucket: `minimal`

## Metric Evidence

```json
{
  "core_metrics": {
    "expected_value_score": 0.5911,
    "signals_generated": 60,
    "signals_survived": 52,
    "survival_rate": 0.8667,
    "total_pnl": 39667.96,
    "trade_count": 22
  },
  "entry_execution_attribution": {
    "candidate_events": 52,
    "entered_count": 22,
    "gap_related_skip_count": 6,
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
      },
      {
        "available_slots_at_entry_loop": 1,
        "candidate_rank": null,
        "date": "2024-11-01",
        "decision": "scarce_slot_breakout_deferred",
        "details": {
          "active_positions": 4,
          "defer_breakout_max_min_index_pct_from_ma": null,
          "defer_breakout_slots_lte": 1,
          "min_index_pct_from_ma": null
        },
        "strategy": "breakout_long",
        "ticker": "CVX"
      },
      {
        "available_slots_at_entry_loop": 1,
        "candidate_rank": 1,
        "date": "2024-11-06",
        "decision": "no_shares",
        "details": {
          "has_sizing": true,
          "risk_multipliers": {
            "trend_industrials_risk_multiplier_applied": 0.0,
            "trend_mid_sector_dispersion_risk_multiplier_applied": 1.25
          },
          "risk_pct_after": null,
          "risk_pct_before": null,
          "shares_to_buy": 0
        },
        "strategy": "trend_long",
        "ticker": "CAT"
      },
      {
        "available_slots_at_entry_loop": 1,
        "candidate_rank": 2,
        "date": "2024-11-06",
        "decision": "slot_sliced",
        "details": {
          "signal_count": 6
        },
        "strategy": "trend_long",
        "ticker": "GS"
      }
    ],
    "skip_rate": 0.5769,
    "skipped_count": 30
  },
  "evidence_type": "latest_backtest_entry_execution_attribution",
  "limitation": "This quantifies skipped entry decisions in replay, but live planned-vs-actual timestamps and realized fill slippage are still missing.",
  "period": "2024-10-02 \u2192 2025-04-22",
  "source_backtest": "data/backtests/backtest_results_20260520.json"
}
```

## Next Evidence Needed

Add live planned-vs-actual timestamp and fill telemetry before testing one shared execution policy variable.
