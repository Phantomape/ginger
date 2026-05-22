# exp-20260522-008 event core independence context

## Hypothesis
Event overlay rows that are independent of active core positions have higher replacement value than rows duplicating existing core exposure, so a small independent-context notional scalar may improve expected_value_score without adding noisy tickers.

## Trial accounting
```json
{
  "changed_variable": "event_core_independent_notional_scalar",
  "multiple_testing_risk_bucket": "moderate",
  "nearby_prior_experiments": [
    "exp-20260521-019_event_attention_persistence_rejected_sparse_repeat_context",
    "exp-20260521-020_event_same_day_core_overlap_signal_rejected_sparse_probe",
    "exp-20260522-007_event_governance_503_haircut_accepted"
  ],
  "new_evidence_type": "new_core_backtest_overlap_context_after_exp007",
  "prior_trial_count": 1,
  "trial_family": "event_overlay_replacement_value_core_overlap_context"
}
```

## Baseline
- variant: baseline_exp007
- aggregate expected_value_score: 19.6758
- aggregate total_pnl: 439820.3

## Best replay variant
- variant: core_independent_115
- config: `{"core_independent_scalar": 1.15}`
- aggregate expected_value_score: 21.1917
- aggregate total_pnl: 470944.85
- gate4 passed: False
- decision: rejected_failed_gate4

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "notes": "No strategy behavior was changed. Positive replay evidence requires a shared core-position context adapter before promotion.",
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Gate 4
```json
{
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0007,
      "ev_delta_pct": 0.054059,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.047649,
      "sharpe_daily_delta": 0.03,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0033,
      "ev_delta_pct": 0.095245,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.088764,
      "sharpe_daily_delta": 0.03,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": -0.0221,
      "ev_delta_pct": 0.087273,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.077163,
      "sharpe_daily_delta": 0.02,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "delta": {
    "after_ev_sum": 21.1917,
    "after_pnl_sum": 470944.85,
    "aggregate_ev_delta": 1.5159,
    "aggregate_ev_delta_pct": 0.077044,
    "aggregate_pnl_delta": 31124.55,
    "aggregate_pnl_delta_pct": 0.070767,
    "baseline_ev_sum": 19.6758,
    "baseline_pnl_sum": 439820.3,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.4528,
        "max_drawdown_pct": -0.0007,
        "sharpe_daily": 0.03,
        "survival_rate": 0.0,
        "total_pnl": 8128.62,
        "total_return_pct": 0.0813,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.9193,
        "max_drawdown_pct": -0.0033,
        "sharpe_daily": 0.03,
        "survival_rate": 0.0,
        "total_pnl": 16998.88,
        "total_return_pct": 0.17,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": 0.1438,
        "max_drawdown_pct": 0.0221,
        "sharpe_daily": 0.02,
        "survival_rate": 0.0,
        "total_pnl": 5997.05,
        "total_return_pct": 0.06,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 3,
    "windows_pnl_regressed": 0
  },
  "max_drawdown_drift_limit": 0.02,
  "max_window_drawdown_drift": 0.0221,
  "passed": false,
  "risk_guard": {
    "max_allowed_drawdown_drift": 0.02,
    "max_drawdown_drift": 0.0221,
    "passed": false
  },
  "risk_guard_passed": false,
  "rule": "EV first over the three canonical backtesting.md windows; require majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger.",
  "sample_guard": {
    "max_single_positive_share": 0.35,
    "max_top5_positive_share": 0.7,
    "min_target_trades": 15,
    "min_tickers": 10,
    "min_win_rate": 0.6,
    "min_windows": 3,
    "passed": false,
    "target_max_single_positive_share": 0.4102,
    "target_ticker_count": 15,
    "target_top5_positive_share": 0.9476,
    "target_total_pnl": 211499.28,
    "target_trade_count": 24,
    "target_win_rate": 0.7917,
    "target_windows_present": [
      "late_strong",
      "mid_weak",
      "old_thin"
    ]
  },
  "sample_guard_passed": false
}
```
