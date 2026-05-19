# Form 4 Single-Owner Pre-Entry RS

- experiment_id: `exp-20260512-108`
- timestamp: `2026-05-12T20:07:03+00:00`
- decision: `rejected_positive_vs_core_but_not_single_owner`

## Hypothesis

PIT-safe single-owner Form 4 forward-queue events may be higher-quality when the ticker already outperformed SPY over the 5 trading days before the paper entry; this can separate informed accumulation from stale insider purchases without adding noisy tickers or LLM ranking.

## Three-Window Results

| Window | Core EV | Single-owner EV | Confirmed EV | Delta vs single | Delta vs core | Core PnL | Confirmed PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.234 | 4.3567 | 4.3504 | -0.0063 | 0.1164 | $94,086.91 | $96,461.93 | $1,660.86 | 19 -> 21 |
| mid_weak | 1.6689 | 1.865 | 1.764 | -0.101 | 0.0951 | $61,813.40 | $63,453.35 | $1,382.88 | 21 -> 24 |
| old_thin | 0.3853 | 0.3854 | 0.3853 | -0.0001 | 0.0 | $28,544.11 | $28,544.11 | $0.00 | 22 -> 22 |

## Aggregate Vs Single-Owner

```json
{
  "after_ev_sum": 6.4997,
  "after_pnl_sum": 188459.39,
  "aggregate_ev_delta": -0.1074,
  "aggregate_ev_delta_pct": -0.016255,
  "aggregate_pnl_delta": -1900.0,
  "aggregate_pnl_delta_pct": -0.009981,
  "before_ev_sum": 6.6071,
  "before_pnl_sum": 190359.39,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 3,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 3
}
```

## Aggregate Vs Core

```json
{
  "after_ev_sum": 6.4997,
  "after_pnl_sum": 188459.39,
  "aggregate_ev_delta": 0.2115,
  "aggregate_ev_delta_pct": 0.033634,
  "aggregate_pnl_delta": 4014.97,
  "aggregate_pnl_delta_pct": 0.021768,
  "before_ev_sum": 6.2882,
  "before_pnl_sum": 184444.42,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 2,
  "windows_pnl_regressed": 0
}
```

## Gate

```json
{
  "by_window_vs_core": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.027492,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.025243,
      "sharpe_daily_delta": 0.01,
      "trade_count_increased_with_win_rate_not_down": true
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0014,
      "ev_delta_pct": 0.056984,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.026531,
      "sharpe_daily_delta": 0.08,
      "trade_count_increased_with_win_rate_not_down": true
    },
    "old_thin": {
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
    }
  },
  "by_window_vs_single_owner": {
    "late_strong": {
      "drawdown_improvement_pct": 0.0002,
      "ev_delta_pct": -0.001446,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.001436,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "mid_weak": {
      "drawdown_improvement_pct": -0.001,
      "ev_delta_pct": -0.054155,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.026916,
      "sharpe_daily_delta": -0.08,
      "trade_count_increased_with_win_rate_not_down": false
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": -0.000259,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": false,
      "pnl_delta_pct": -0.000214,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": false
    }
  },
  "confirmed_selected_event_trades": 5,
  "improves_vs_single_owner": false,
  "material_vs_core": false,
  "no_core_ev_regression": true,
  "passed": false,
  "sample_guard_min_trades": 8,
  "sample_guard_passed": false,
  "single_ticker_positive_share": 0.4334,
  "single_ticker_positive_share_guard": "<= 0.50"
}
```

## Decision

The 5d pre-entry RS qualifier stayed positive versus core but failed to improve the latest single-owner Form 4 baseline enough to justify a new event qualification rule.

## Production Impact

{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "live_slots_changed": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "promotion_blocker_if_positive": "A shared default-off Form 4 pre-entry RS queue/paper adapter must be wired in run.py and replay before any trade-enabled promotion.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}

