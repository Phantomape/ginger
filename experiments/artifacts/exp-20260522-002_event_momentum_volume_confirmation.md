# exp-20260522-002 Event Momentum Plus Volume Confirmation

Decision: `rejected_event_momentum_volume_confirmation_context`

## Hypothesis

Inside the accepted default-off event overlay, rows with both positive 20-day excess return versus SPY and 20-day volume confirmation may retain the replacement value seen in the single-field momentum and volume scouts while reducing drawdown from over-broad participation.

## Variant Deltas Vs Accepted Event Baseline

| Variant | Passed | Sample | Risk | EV delta | PnL delta | EV + / - windows | Max DD drift |
|---|---:|---:|---:|---:|---:|---:|---:|
| momentum_volume_confirmation_105 | no | yes | yes | +0.2814 | $+7,043.16 | 3/0 | 0.0074 |
| momentum_volume_confirmation_110 | no | yes | yes | +0.5725 | $+14,086.35 | 3/0 | 0.0148 |
| momentum_volume_confirmation_115 | no | yes | no | +0.8537 | $+21,129.53 | 3/0 | 0.0220 |
| momentum_volume_confirmation_120 | no | yes | no | +1.1147 | $+28,172.67 | 3/0 | 0.0292 |

## Selection

```json
{
  "rows_with_both_fields_count": 26,
  "target_by_window": {
    "late_strong": {
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "reaction_-2_to_0",
        "reaction_-5_to_-2"
      ],
      "ret20_excess_spy_values": [
        0.176896,
        0.016922,
        0.055842,
        0.17953,
        0.267562
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "DE",
        "GS",
        "ISRG",
        "LITE",
        "MCD"
      ],
      "total_pnl": 59425.91,
      "trade_count": 5,
      "volume_ratio_20_values": [
        3.476546,
        1.194941,
        1.176947,
        2.528554,
        1.559986
      ],
      "wins": 3
    },
    "mid_weak": {
      "reaction_buckets": [
        "reaction_-5_to_-2"
      ],
      "ret20_excess_spy_values": [
        0.419284,
        0.116159
      ],
      "sources": [
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "CRDO"
      ],
      "total_pnl": 62534.16,
      "trade_count": 2,
      "volume_ratio_20_values": [
        5.820001,
        3.309924
      ],
      "wins": 2
    },
    "old_thin": {
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct",
        "reaction_-2_to_0"
      ],
      "ret20_excess_spy_values": [
        0.053032,
        0.282666,
        0.089845,
        0.060717
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "mid_dispersion_selective_leadership"
      ],
      "tickers": [
        "CRDO",
        "GS",
        "RTX"
      ],
      "total_pnl": 47076.15,
      "trade_count": 4,
      "volume_ratio_20_values": [
        1.396533,
        1.120322,
        1.408097,
        1.179588
      ],
      "wins": 3
    }
  },
  "target_fields": [
    "ret20_excess_spy",
    "volume_ratio_20"
  ],
  "target_max_single_positive_pnl_share": 0.3554,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_rule": "ret20_excess_spy > 0.0 and volume_ratio_20 >= 1.1",
  "target_scaled_total_pnl": 169036.22,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation"
  ],
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "mid_dispersion_selective_leadership",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "CRDO",
    "DE",
    "GS",
    "ISRG",
    "LITE",
    "MCD",
    "RTX"
  ],
  "target_trade_count": 11,
  "target_win_rate": 0.7273,
  "target_windows_present": 3,
  "target_wins": 8
}
```

## Gate 4

```json
{
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": -0.0036,
      "ev_delta_pct": 0.043154,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.058371,
      "sharpe_daily_delta": -0.07,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0008,
      "ev_delta_pct": 0.061032,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.054652,
      "sharpe_daily_delta": 0.03,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": -0.0292,
      "ev_delta_pct": 0.125669,
      "passes_drawdown": false,
      "passes_material_ev": true,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.109073,
      "sharpe_daily_delta": 0.03,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "delta": {
    "after_ev_sum": 20.2757,
    "after_pnl_sum": 460490.65,
    "aggregate_ev_delta": 1.1147,
    "aggregate_ev_delta_pct": 0.058175,
    "aggregate_pnl_delta": 28172.67,
    "aggregate_pnl_delta_pct": 0.065167,
    "baseline_ev_sum": 19.161,
    "baseline_pnl_sum": 432317.98,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.3566,
        "max_drawdown_pct": 0.0036,
        "sharpe_daily": -0.07,
        "survival_rate": 0.0,
        "total_pnl": 9904.3,
        "total_return_pct": 0.099,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.5773,
        "max_drawdown_pct": -0.0008,
        "sharpe_daily": 0.03,
        "survival_rate": 0.0,
        "total_pnl": 10422.35,
        "total_return_pct": 0.1043,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": 0.1808,
        "max_drawdown_pct": 0.0292,
        "sharpe_daily": 0.03,
        "survival_rate": 0.0,
        "total_pnl": 7846.02,
        "total_return_pct": 0.0785,
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
  "max_window_drawdown_drift": 0.0292,
  "passed": false,
  "risk_guard_passed": false,
  "rule": "EV first over the three canonical backtesting.md windows; require majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger.",
  "sample_guard": {
    "actual_rows_with_both_fields": 26,
    "actual_target_max_single_positive_pnl_share": 0.3554,
    "actual_target_tickers": [
      "CRDO",
      "DE",
      "GS",
      "ISRG",
      "LITE",
      "MCD",
      "RTX"
    ],
    "actual_target_trades": 11,
    "actual_target_windows": 3,
    "max_target_positive_pnl_share": 0.4,
    "min_rows_with_both_fields": 25,
    "min_target_tickers": 6,
    "min_target_trades": 10,
    "min_target_windows": 3
  },
  "sample_guard_passed": true
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
