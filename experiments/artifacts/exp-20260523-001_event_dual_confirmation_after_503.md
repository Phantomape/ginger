# exp-20260523-001 Event Dual Confirmation After 5.03

Decision: `rejected_event_dual_confirmation_after_503`
Best EV variant: `dual_confirmation_after_503_1150`
Best risk-passing variant: `dual_confirmation_after_503_1125`

## Hypothesis

After the accepted SEC governance 5.03 haircut reduced a fragile event subcohort, event rows with both positive 20-day excess return versus SPY and 20-day volume confirmation may be strong enough to support modest default-off paper allocation without changing source queues, ranking, exits, live orders, or LLM authority.

## Trial Accounting

- trial_family: `event_momentum_volume_confirmation_after_503`
- changed_variable: `event_dual_confirmation_after_503_scalar`
- prior_trial_count: `3`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `new_accepted_event_503_haircut_baseline`

## Variant Deltas Vs Accepted 5.03 Baseline

| Variant | Passed | Sample | Risk | EV delta | PnL delta | EV + / - windows | EV delta pct | PnL delta pct | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|---:|
| dual_confirmation_after_503_1025 | no | yes | yes | +0.1543 | $+3,487.40 | 3/0 | 0.7842% | 0.7929% | 0.0037 |
| dual_confirmation_after_503_1050 | no | yes | yes | +0.3031 | $+6,974.80 | 3/0 | 1.5405% | 1.5858% | 0.0074 |
| dual_confirmation_after_503_1075 | no | yes | yes | +0.4322 | $+10,462.23 | 3/0 | 2.1966% | 2.3788% | 0.0111 |
| dual_confirmation_after_503_1100 | no | yes | yes | +0.5809 | $+13,949.63 | 3/0 | 2.9524% | 3.1717% | 0.0148 |
| dual_confirmation_after_503_1125 | no | yes | yes | +0.7273 | $+17,437.01 | 3/0 | 3.6964% | 3.9646% | 0.0184 |
| dual_confirmation_after_503_1150 | no | yes | no | +0.8759 | $+20,924.45 | 3/0 | 4.4517% | 4.7575% | 0.0220 |

## Target Sample

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
      "total_pnl": 56949.82,
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
      "total_pnl": 59928.57,
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
      "total_pnl": 43542.36,
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
  "target_max_single_positive_pnl_share": 0.3588,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_rule": "ret20_excess_spy > 0.0 and volume_ratio_20 >= 1.1",
  "target_scaled_total_pnl": 160420.75,
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
      "drawdown_improvement_pct": -0.0028,
      "ev_delta_pct": 0.03504,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.043544,
      "sharpe_daily_delta": -0.04,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0005,
      "ev_delta_pct": 0.047006,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.040817,
      "sharpe_daily_delta": 0.03,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": -0.022,
      "ev_delta_pct": 0.078109,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": true,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.073076,
      "sharpe_daily_delta": 0.01,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "delta": {
    "after_ev_sum": 20.5517,
    "after_pnl_sum": 460744.75,
    "aggregate_ev_delta": 0.8759,
    "aggregate_ev_delta_pct": 0.044517,
    "aggregate_pnl_delta": 20924.45,
    "aggregate_pnl_delta_pct": 0.047575,
    "baseline_ev_sum": 19.6758,
    "baseline_pnl_sum": 439820.3,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.2935,
        "max_drawdown_pct": 0.0028,
        "sharpe_daily": -0.04,
        "survival_rate": 0.0,
        "total_pnl": 7428.24,
        "total_return_pct": 0.0743,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.4537,
        "max_drawdown_pct": -0.0005,
        "sharpe_daily": 0.03,
        "survival_rate": 0.0,
        "total_pnl": 7816.77,
        "total_return_pct": 0.0781,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": 0.1287,
        "max_drawdown_pct": 0.022,
        "sharpe_daily": 0.01,
        "survival_rate": 0.0,
        "total_pnl": 5679.44,
        "total_return_pct": 0.0568,
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
  "max_window_drawdown_drift": 0.022,
  "passed": false,
  "risk_guard_passed": false,
  "rule": "EV first over the three canonical backtesting.md windows; require majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger.",
  "sample_guard": {
    "actual_rows_with_both_fields": 26,
    "actual_target_max_single_positive_pnl_share": 0.3588,
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

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "live_orders_enabled": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "promotion_required_if_accepted": "Move the dual-confirmation event notional scalar into shared event_sleeve_bundle metadata/config and report it through run.py with focused parity tests before any production paper behavior changes.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

## Closeout

Rejected: after the 5.03 haircut, dual confirmation stayed directionally positive but still did not clear the event Gate 4 materiality/risk tradeoff under high multiple-testing risk.

No JavaScript was used.
