# exp-20260522-001 Event Low-Extension Context

Decision: `rejected_event_low_extension_context`

## Hypothesis

Inside the accepted default-off event overlay, event rows with low short-term extension (`state_features.ret5 <= 0.02`) may carry cleaner replacement value than already-extended event rows. A single paper-notional scalar tests this production-visible extension field without changing core trades.

## Variant Deltas Vs Accepted Event Baseline

| Variant | Passed | Sample | Risk | EV delta | PnL delta | EV + / - windows | Max DD drift |
|---|---:|---:|---:|---:|---:|---:|---:|
| low_extension_context_080 | no | no | yes | -0.0853 | $-2,905.59 | 2/1 | -0.0001 |
| low_extension_context_090 | no | no | yes | -0.0414 | $-1,452.81 | 2/1 | 0.0000 |
| low_extension_context_105 | no | no | yes | +0.0000 | $+726.39 | 1/2 | 0.0000 |
| low_extension_context_110 | no | no | yes | +0.0166 | $+1,452.81 | 1/2 | 0.0001 |
| low_extension_context_115 | no | no | yes | +0.0403 | $+2,179.20 | 1/2 | 0.0001 |
| low_extension_context_120 | no | no | yes | +0.0399 | $+2,905.59 | 1/2 | 0.0001 |
| low_extension_context_125 | no | no | yes | +0.0435 | $+3,631.99 | 1/2 | 0.0002 |

## Selection

```json
{
  "rows_with_field_count": 26,
  "target_by_window": {
    "late_strong": {
      "reaction_buckets": [
        "positive_excess_0_to_2pct",
        "reaction_-2_to_0"
      ],
      "ret5_values": [
        -0.013292,
        -0.015329
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence"
      ],
      "tickers": [
        "MCD",
        "NFLX"
      ],
      "total_pnl": -1108.22,
      "trade_count": 2,
      "wins": 1
    },
    "mid_weak": {
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "reaction_-2_to_0"
      ],
      "ret5_values": [
        -0.015091,
        -0.000528,
        -0.018045,
        -0.004625,
        -0.052305,
        -0.01105
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation",
        "narrow_cap_weight_leadership",
        "weak_index"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "DIS",
        "GS",
        "MCD",
        "NOW",
        "TRIP"
      ],
      "total_pnl": 30308.78,
      "trade_count": 6,
      "wins": 5
    },
    "old_thin": {
      "reaction_buckets": [
        "positive_excess_0_to_2pct",
        "reaction_-2_to_0"
      ],
      "ret5_values": [
        -0.023613,
        -0.020683,
        0.011726,
        0.00603,
        0.007089
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "mid_dispersion_selective_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "GS",
        "MCD",
        "RTX"
      ],
      "total_pnl": -6037.49,
      "trade_count": 5,
      "wins": 4
    }
  },
  "target_field": "state_features.ret5",
  "target_max_single_positive_pnl_share": 0.7007,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0"
  ],
  "target_rule": "ret5 <= 0.02",
  "target_scaled_total_pnl": 23163.07,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation",
    "narrow_cap_weight_leadership",
    "weak_index"
  ],
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "mid_dispersion_selective_leadership",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "DIS",
    "GS",
    "MCD",
    "NFLX",
    "NOW",
    "RTX",
    "TRIP"
  ],
  "target_trade_count": 13,
  "target_win_rate": 0.7692,
  "target_windows_present": 3,
  "target_wins": 10
}
```

## Gate 4

```json
{
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": -0.0001,
      "ev_delta_pct": -0.005409,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.001306,
      "sharpe_daily_delta": -0.02,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": -0.0002,
      "ev_delta_pct": 0.014124,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.026539,
      "sharpe_daily_delta": -0.06,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": -0.031556,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.016786,
      "sharpe_daily_delta": -0.03,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "delta": {
    "after_ev_sum": 19.2045,
    "after_pnl_sum": 435949.97,
    "aggregate_ev_delta": 0.0435,
    "aggregate_ev_delta_pct": 0.00227,
    "aggregate_pnl_delta": 3631.99,
    "aggregate_pnl_delta_pct": 0.008401,
    "baseline_ev_sum": 19.161,
    "baseline_pnl_sum": 432317.98,
    "by_window": {
      "late_strong": {
        "expected_value_score": -0.0447,
        "max_drawdown_pct": 0.0001,
        "sharpe_daily": -0.02,
        "survival_rate": 0.0,
        "total_pnl": -221.64,
        "total_return_pct": -0.0022,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.1336,
        "max_drawdown_pct": 0.0002,
        "sharpe_daily": -0.06,
        "survival_rate": 0.0,
        "total_pnl": 5061.14,
        "total_return_pct": 0.0507,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": -0.0454,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": -0.03,
        "survival_rate": 0.0,
        "total_pnl": -1207.51,
        "total_return_pct": -0.012,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "windows_ev_improved": 1,
    "windows_ev_regressed": 2,
    "windows_pnl_improved": 1,
    "windows_pnl_regressed": 2
  },
  "max_drawdown_drift_limit": 0.02,
  "max_window_drawdown_drift": 0.0002,
  "passed": false,
  "risk_guard_passed": true,
  "rule": "EV first over the three canonical backtesting.md windows; require majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger.",
  "sample_guard": {
    "actual_rows_with_field": 26,
    "actual_target_max_single_positive_pnl_share": 0.7007,
    "actual_target_tickers": [
      "DIS",
      "GS",
      "MCD",
      "NFLX",
      "NOW",
      "RTX",
      "TRIP"
    ],
    "actual_target_trades": 13,
    "actual_target_windows": 3,
    "max_target_positive_pnl_share": 0.45,
    "min_rows_with_field": 25,
    "min_target_tickers": 6,
    "min_target_trades": 10,
    "min_target_windows": 3
  },
  "sample_guard_passed": false
}
```

## Production Impact

```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: False
  parity_test_added: False
```

No shared production policy was changed because Gate 4 failed.
