# exp-20260522-020 Event Narrow-Cap Leadership Haircut

Decision: `rejected_event_narrow_cap_leadership_haircut`
Best variant: `narrow_cap_leadership_025`

## Hypothesis

Default-off event rows that fire during narrow cap-weight leadership may represent crowded, fragile leadership rather than durable event alpha; a small paper-notional haircut could improve replacement value without changing source queues, ranking, exits, or live orders.

## Trial Accounting

- trial_family: `event_market_state_crowding_context`
- changed_variable: `event_narrow_cap_weight_leadership_scalar`
- prior_trial_count: `1`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `narrower_production_visible_state_bucket_after_503_haircut`

## Variant Sweep

| Variant | Scalar | Passed | Sample | Materiality | Risk | dEV | dPnL | EV +/- | Max DD drift |
|---|---:|:---:|:---:|:---:|:---:|---:|---:|---:|---:|
| narrow_cap_leadership_075 | 0.75 | no | no | no | yes | +0.0528 | $+746.26 | 3/0 | +0.0000 |
| narrow_cap_leadership_050 | 0.50 | no | no | no | yes | +0.1001 | $+1,492.52 | 3/0 | +0.0000 |
| narrow_cap_leadership_025 | 0.25 | no | no | no | yes | +0.1646 | $+2,238.78 | 3/0 | +0.0000 |
| narrow_cap_leadership_000 | 0.00 | no | no | no | no | -3.9373 | $-37,154.96 | 0/3 | +0.0169 |

## Best Variant Window Deltas

| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta |
|---|---:|---:|---:|---:|---:|
| late_strong | +0.0454 | $+228.35 | +0.0023 | +0.02 | -0.0001 |
| mid_weak | +0.0495 | $+222.19 | +0.0022 | +0.02 | -0.0002 |
| old_thin | +0.0697 | $+1,788.24 | +0.0179 | +0.04 | +0.0000 |

## Target Sample

```json
{
  "target_by_window": {
    "late_strong": {
      "eight_k_item_code_sets": [
        "5.03|9.01"
      ],
      "losses": 1,
      "reaction_buckets": [
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_surfaces": [
        "balanced_state_leadership"
      ],
      "tickers": [
        "NFLX"
      ],
      "total_pnl": -304.47,
      "trade_count": 1,
      "wins": 0
    },
    "mid_weak": {
      "eight_k_item_code_sets": [
        "",
        "5.03|5.07|9.01"
      ],
      "losses": 1,
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "reaction_-2_to_0"
      ],
      "semantic_subcategories": [
        "",
        "shareholder_vote"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence"
      ],
      "tickers": [
        "DIS",
        "NOW"
      ],
      "total_pnl": -296.24,
      "trade_count": 2,
      "wins": 1
    },
    "old_thin": {
      "eight_k_item_code_sets": [
        "5.03|9.01"
      ],
      "losses": 1,
      "reaction_buckets": [
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence"
      ],
      "tickers": [
        "GS"
      ],
      "total_pnl": -2384.32,
      "trade_count": 1,
      "wins": 0
    }
  },
  "target_field": "event_state_bucket_narrow_cap_weight_leadership",
  "target_losses": 3,
  "target_max_single_loss_pnl_share": 0.6954,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0"
  ],
  "target_rule": "state_bucket == narrow_cap_weight_leadership",
  "target_scaled_total_pnl": -2985.03,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence"
  ],
  "target_tickers": [
    "DIS",
    "GS",
    "NFLX",
    "NOW"
  ],
  "target_trade_count": 4,
  "target_win_rate": 0.25,
  "target_windows_present": 3,
  "target_wins": 1
}
```

## Gate 4

```json
{
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0001,
      "ev_delta_pct": 0.00542,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.001339,
      "sharpe_daily_delta": 0.02,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0002,
      "ev_delta_pct": 0.005128,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.00116,
      "sharpe_daily_delta": 0.02,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.042301,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.023009,
      "sharpe_daily_delta": 0.04,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "delta": {
    "after_ev_sum": 19.8404,
    "after_pnl_sum": 442059.08,
    "aggregate_ev_delta": 0.1646,
    "aggregate_ev_delta_pct": 0.008366,
    "aggregate_pnl_delta": 2238.78,
    "aggregate_pnl_delta_pct": 0.00509,
    "baseline_ev_sum": 19.6758,
    "baseline_pnl_sum": 439820.3,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.0454,
        "max_drawdown_pct": -0.0001,
        "sharpe_daily": 0.02,
        "survival_rate": 0.0,
        "total_pnl": 228.35,
        "total_return_pct": 0.0023,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.0495,
        "max_drawdown_pct": -0.0002,
        "sharpe_daily": 0.02,
        "survival_rate": 0.0,
        "total_pnl": 222.19,
        "total_return_pct": 0.0022,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": 0.0697,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.04,
        "survival_rate": 0.0,
        "total_pnl": 1788.24,
        "total_return_pct": 0.0179,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 3,
    "windows_pnl_regressed": 0
  },
  "materiality_guard": {
    "aggregate_ev_delta_pct": 0.008366,
    "aggregate_pnl_delta_pct": 0.00509,
    "min_delta_pct": 0.02
  },
  "materiality_guard_passed": false,
  "max_drawdown_drift_limit": 0.01,
  "max_window_drawdown_drift": 0.0,
  "passed": false,
  "risk_guard_passed": true,
  "rule": "EV first over the three canonical backtesting.md windows; require majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger.",
  "sample_guard": {
    "actual_target_losses": 3,
    "actual_target_max_single_loss_pnl_share": 0.6954,
    "actual_target_scaled_total_pnl": -2985.03,
    "actual_target_tickers": [
      "DIS",
      "GS",
      "NFLX",
      "NOW"
    ],
    "actual_target_trades": 4,
    "actual_target_windows": 3,
    "max_target_single_loss_pnl_share": 0.75,
    "min_target_losses": 3,
    "min_target_tickers": 4,
    "min_target_trades": 5,
    "min_target_windows": 3,
    "requires_negative_baseline_target_pnl": true
  },
  "sample_guard_passed": false,
  "three_window_guard_passed": false
}
```

## Production Impact

```text
production_impact:
  shared_policy_changed: False
  backtester_adapter_changed: False
  run_adapter_changed: False
  replay_only: True
  parity_test_added: False
  alters_orders: False
```

No shared policy or live/default order behavior changed.

No JavaScript was used.
