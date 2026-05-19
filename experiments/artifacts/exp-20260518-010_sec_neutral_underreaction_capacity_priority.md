# exp-20260518-010 SEC Neutral-Underreaction Capacity Priority

Decision: `rejected_sec_neutral_underreaction_capacity_priority`.

## Gate 4

```json
{
  "aggregate_delta": {
    "expected_value_score_sum_delta": 0.102431,
    "expected_value_score_sum_delta_pct": 0.009312,
    "max_drawdown_pct_max_delta": 0.000858,
    "max_drawdown_pct_max_delta_pct": 0.007654,
    "min_survival_rate_delta": 0.0,
    "min_survival_rate_delta_pct": 0.0,
    "sleeve_closed_trade_count_sum_delta": 0.0,
    "sleeve_closed_trade_count_sum_delta_pct": 0.0,
    "sleeve_total_pnl_sum_delta": 2275.62,
    "sleeve_total_pnl_sum_delta_pct": 0.034919,
    "total_pnl_sum_delta": 2275.62,
    "total_pnl_sum_delta_pct": 0.007535,
    "trade_count_sum_delta": 0.0,
    "trade_count_sum_delta_pct": 0.0
  },
  "ev_positive_windows": 2,
  "ev_regressed_windows": 0,
  "max_drawdown_delta_max": 0.000858,
  "metric_gate_passed": false,
  "passed": false,
  "pnl_positive_windows": 2,
  "pnl_regressed_windows": 0,
  "rule": "Pass if aggregate EV/PnL improve versus exp-20260518-009, EV and PnL improve in all three fixed windows, no window regresses, max drawdown worsens by no more than 0.5 percentage points, target neutral-underreaction trades >= 6, and target trades are present in all 3 windows.",
  "sample_guard_passed": true,
  "window_checks": {
    "late_strong": {
      "ev_delta": 0.032759,
      "max_drawdown_delta": -0.000156,
      "neutral_underreaction_closed_trade_count": 2,
      "neutral_underreaction_pnl_delta": -206.64,
      "pnl_delta": 346.03,
      "sleeve_trade_count_delta": 0
    },
    "mid_weak": {
      "ev_delta": 0.0,
      "max_drawdown_delta": 0.0,
      "neutral_underreaction_closed_trade_count": 2,
      "neutral_underreaction_pnl_delta": 0.0,
      "pnl_delta": 0.0,
      "sleeve_trade_count_delta": 0
    },
    "old_thin": {
      "ev_delta": 0.069672,
      "max_drawdown_delta": 0.000858,
      "neutral_underreaction_closed_trade_count": 6,
      "neutral_underreaction_pnl_delta": 498.61,
      "pnl_delta": 1929.59,
      "sleeve_trade_count_delta": 0
    }
  }
}
```

## Selection Diff

```json
{
  "added_count": 3,
  "added_target_rows": [
    {
      "adjusted_pnl": -206.64,
      "baseline_pnl": -103.32,
      "entry_date": "2025-10-31",
      "event_family": "earnings_8k",
      "exit_date": "2025-11-14",
      "form_base": "8-K",
      "incremental_pnl": -103.32,
      "language_bucket": "neutral_or_mixed_language",
      "spy_t1_return": -0.010998,
      "t1_excess_return_vs_spy": 0.011855,
      "t1_return": 0.000857,
      "ticker": "BKNG",
      "window": "late_strong"
    },
    {
      "adjusted_pnl": -373.85,
      "baseline_pnl": -186.93,
      "entry_date": "2025-02-03",
      "event_family": "earnings_8k",
      "exit_date": "2025-02-18",
      "form_base": "8-K",
      "incremental_pnl": -186.93,
      "language_bucket": "neutral_or_mixed_language",
      "spy_t1_return": -0.005322,
      "t1_excess_return_vs_spy": 0.010881,
      "t1_return": 0.005559,
      "ticker": "NOW",
      "window": "old_thin"
    },
    {
      "adjusted_pnl": 872.46,
      "baseline_pnl": 436.23,
      "entry_date": "2025-02-04",
      "event_family": "earnings_8k",
      "exit_date": "2025-02-19",
      "form_base": "8-K",
      "incremental_pnl": 436.23,
      "language_bucket": "neutral_or_mixed_language",
      "spy_t1_return": -0.00673,
      "t1_excess_return_vs_spy": 0.018491,
      "t1_return": 0.011761,
      "ticker": "V",
      "window": "old_thin"
    }
  ],
  "common_target_count": 7,
  "removed_count": 0,
  "removed_target_rows": []
}
```

No JavaScript was used.
