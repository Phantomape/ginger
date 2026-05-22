# exp-20260522-009 event_operational_specificity_flag

## Hypothesis
Inside the accepted default-off event overlay, SEC event rows whose archived filing text contains concrete operating or financial specificity may have higher replacement value than generic event rows. A single paper-notional scalar tests that disclosure-quality field without touching core entries, exits, ranking, or source capacity.

## Trial accounting
```json
{
  "changed_variable": "event_operational_specificity_scalar",
  "multiple_testing_risk_bucket": "moderate",
  "nearby_prior_experiments": [
    "exp-20260521-016",
    "exp-20260521-019",
    "exp-20260522-007",
    "exp-20260522-008"
  ],
  "new_evidence_type": "new_historical_sec_text_specificity_field",
  "prior_trial_count": 1,
  "trial_family": "event_operational_specificity_disclosure_quality"
}
```

## Best variant
- variant: `operational_specificity_120`
- scalar: `1.2`
- aggregate EV delta: `1.0907`
- aggregate PnL delta: `20827.33`
- decision: `rejected_event_operational_specificity_flag`

## Gate 4
```json
{
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0003,
      "ev_delta_pct": 0.063216,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.061051,
      "sharpe_daily_delta": 0.01,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0009,
      "ev_delta_pct": 0.059242,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.055059,
      "sharpe_daily_delta": 0.02,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": -0.0009,
      "ev_delta_pct": -0.006433,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.001695,
      "sharpe_daily_delta": -0.01,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "delta": {
    "after_ev_sum": 20.7665,
    "after_pnl_sum": 460647.63,
    "aggregate_ev_delta": 1.0907,
    "aggregate_ev_delta_pct": 0.055434,
    "aggregate_pnl_delta": 20827.33,
    "aggregate_pnl_delta_pct": 0.047354,
    "baseline_ev_sum": 19.6758,
    "baseline_pnl_sum": 439820.3,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.5295,
        "max_drawdown_pct": -0.0003,
        "sharpe_daily": 0.01,
        "survival_rate": 0.0,
        "total_pnl": 10414.92,
        "total_return_pct": 0.1042,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.5718,
        "max_drawdown_pct": -0.0009,
        "sharpe_daily": 0.02,
        "survival_rate": 0.0,
        "total_pnl": 10544.14,
        "total_return_pct": 0.1054,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": -0.0106,
        "max_drawdown_pct": 0.0009,
        "sharpe_daily": -0.01,
        "survival_rate": 0.0,
        "total_pnl": -131.73,
        "total_return_pct": -0.0013,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "windows_ev_improved": 2,
    "windows_ev_regressed": 1,
    "windows_pnl_improved": 2,
    "windows_pnl_regressed": 1
  },
  "max_drawdown_drift_limit": 0.02,
  "max_window_drawdown_drift": 0.0009,
  "passed": false,
  "risk_guard_passed": true,
  "rule": "EV first over the three canonical backtesting.md windows; require majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger.",
  "sample_guard": {
    "actual_target_max_single_positive_pnl_share": 0.4639,
    "actual_target_scaled_total_pnl": 108139.09,
    "actual_target_tickers": [
      "CRDO",
      "DE",
      "DIS",
      "GS",
      "ISRG",
      "LITE",
      "MCD",
      "RTX"
    ],
    "actual_target_trades": 14,
    "actual_target_win_rate": 0.8571,
    "actual_target_windows": 3,
    "max_target_positive_pnl_share": 0.45,
    "min_target_tickers": 6,
    "min_target_trades": 10,
    "min_target_win_rate": 0.55,
    "min_target_windows": 3,
    "requires_positive_baseline_target_pnl": true
  },
  "sample_guard_passed": false
}
```

## Production impact
```json
{
  "backtester_adapter_changed": false,
  "notes": "No strategy behavior was changed in this experiment. Any positive result must first be promoted through a shared SEC text-derived candidate field and default-off event_sleeve_bundle adapter before it can affect production paper accounting.",
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```
