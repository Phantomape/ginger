# exp-20260523-005 Event Core-Overlap Haircut

Decision: `rejected_event_core_overlap_haircut`.

## Hypothesis
Default-off event overlay rows that duplicate an active same-ticker core position may have lower incremental replacement value than independent event rows; applying a bounded paper-notional haircut to overlap rows could improve EV and risk without changing event eligibility, source queues, ranking, exits, live orders, LLM, or news.

## Trial Accounting
- trial_family: `event_overlay_replacement_value_core_overlap_context`
- changed_variable: `event_core_overlap_notional_scalar`
- prior_trial_count: `2`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `new_overlap_side_of_existing_core_context_field`

## Three-Window Result
- baseline EV: `19.6475`
- best EV: `20.0046`
- EV delta: `0.3571`
- PnL delta: `$1758.33`
- best variant: `core_overlap_050`

## Gate 4
```json
{
  "by_window": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0097,
      "ev_delta_pct": 0.037389,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": true,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.004656,
      "sharpe_daily_delta": 0.16,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.0,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.0,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.026704,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": 0.012407,
      "sharpe_daily_delta": 0.03,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "delta": {
    "after_ev_sum": 20.0046,
    "after_pnl_sum": 441394.6,
    "aggregate_ev_delta": 0.3571,
    "aggregate_ev_delta_pct": 0.018175,
    "aggregate_pnl_delta": 1758.33,
    "aggregate_pnl_delta_pct": 0.004,
    "baseline_ev_sum": 19.6475,
    "baseline_pnl_sum": 439636.27,
    "by_window": {
      "late_strong": {
        "expected_value_score": 0.3131,
        "max_drawdown_pct": -0.0097,
        "sharpe_daily": 0.16,
        "survival_rate": 0.0,
        "total_pnl": 794.03,
        "total_return_pct": 0.008,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "mid_weak": {
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.0,
        "survival_rate": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "trade_count": 0.0,
        "win_rate": 0.0
      },
      "old_thin": {
        "expected_value_score": 0.044,
        "max_drawdown_pct": 0.0,
        "sharpe_daily": 0.03,
        "survival_rate": 0.0,
        "total_pnl": 964.3,
        "total_return_pct": 0.0096,
        "trade_count": 0.0,
        "win_rate": 0.0
      }
    },
    "windows_ev_improved": 2,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 2,
    "windows_pnl_regressed": 0
  },
  "metric_guard": {
    "aggregate_ev_delta": 0.3571,
    "aggregate_pnl_delta": 1758.33,
    "improved_windows": [
      "late_strong",
      "old_thin"
    ],
    "passed": true,
    "regressed_windows": [],
    "windows_ev_improved": 2,
    "windows_ev_regressed": 0
  },
  "passed": false,
  "risk_guard": {
    "max_allowed_drawdown_drift": 0.02,
    "max_drawdown_drift": 0.0,
    "min_survival_after": 0.7925,
    "min_survival_required": 0.05,
    "passed": true
  },
  "rule": "EV first over the three canonical backtesting.md windows; require majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger.",
  "sample_guard": {
    "max_single_positive_share": 1.0,
    "min_target_trades": 8,
    "min_tickers": 4,
    "min_windows": 2,
    "passed": false,
    "target_ticker_count": 1,
    "target_total_pnl": -3516.62,
    "target_trade_count": 3,
    "target_win_rate": 0.3333,
    "target_windows_present": [
      "late_strong",
      "old_thin"
    ],
    "top5_positive_share": 1.0
  },
  "window_deltas": {
    "late_strong": {
      "expected_value_score": 0.3131,
      "max_drawdown_pct": -0.0097,
      "sharpe_daily": 0.16,
      "strategy_total_return_pct": 0.0,
      "survival_rate": 0.0,
      "total_pnl": 794.03,
      "trade_count": 0.0,
      "win_rate": 0.0
    },
    "mid_weak": {
      "expected_value_score": 0.0,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.0,
      "strategy_total_return_pct": 0.0,
      "survival_rate": 0.0,
      "total_pnl": 0.0,
      "trade_count": 0.0,
      "win_rate": 0.0
    },
    "old_thin": {
      "expected_value_score": 0.044,
      "max_drawdown_pct": 0.0,
      "sharpe_daily": 0.03,
      "strategy_total_return_pct": 0.0,
      "survival_rate": 0.0,
      "total_pnl": 964.3,
      "trade_count": 0.0,
      "win_rate": 0.0
    }
  }
}
```

## Production Impact
```json
{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "production_orders_changed": false,
  "promotion_requirement": "If accepted later, move the core-overlap context into a shared event_sleeve_bundle/run.py-visible adapter and add parity tests.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
