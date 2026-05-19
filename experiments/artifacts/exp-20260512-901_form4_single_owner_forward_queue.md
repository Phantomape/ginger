# Form 4 Single-Owner Forward Queue

- experiment_id: `exp-20260512-901`
- timestamp: `2026-05-12T18:23:00+00:00`
- decision: `rejected_positive_sample_not_material`

## Hypothesis

PIT-safe Form 4 forward-queue events with exactly one reporting owner may be a cleaner standalone insider-buying alpha than multi-owner clusters, because a focused open-market purchase can signal individual conviction while clustered filings may reflect compensation or corporate governance timing rather than incremental replacement value.

## Three-Window Results

| Window | Core EV | Raw Form4 EV | Single-owner EV | Delta vs raw | Delta vs core | Core PnL | Single-owner PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.234 | 4.3567 | 4.3567 | 0.0 | 0.1227 | $94,086.91 | $96,600.69 | $1,799.63 | 19 -> 22 |
| mid_weak | 1.6689 | 1.7937 | 1.865 | 0.0713 | 0.1961 | $61,813.40 | $65,208.48 | $3,138.00 | 21 -> 25 |
| old_thin | 0.3853 | 0.3854 | 0.3854 | 0.0 | 0.0001 | $28,544.11 | $28,550.22 | $6.11 | 22 -> 23 |

## Aggregate vs Raw Form4

```json
{
  "after_ev_sum": 6.6071,
  "after_pnl_sum": 190359.39,
  "aggregate_ev_delta": 0.0713,
  "aggregate_ev_delta_pct": 0.010909,
  "aggregate_pnl_delta": 1146.7,
  "aggregate_pnl_delta_pct": 0.00606,
  "before_ev_sum": 6.5358,
  "before_pnl_sum": 189212.69,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 1,
  "windows_pnl_regressed": 0
}
```

## Aggregate vs Core

```json
{
  "after_ev_sum": 6.6071,
  "after_pnl_sum": 190359.39,
  "aggregate_ev_delta": 0.3189,
  "aggregate_ev_delta_pct": 0.050714,
  "aggregate_pnl_delta": 5914.97,
  "aggregate_pnl_delta_pct": 0.032069,
  "before_ev_sum": 6.2882,
  "before_pnl_sum": 184444.42,
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Gate

```json
{
  "by_window_vs_core": {
    "late_strong": {
      "drawdown_improvement_pct": -0.0002,
      "ev_delta_pct": 0.02898,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.026718,
      "sharpe_daily_delta": 0.01,
      "trade_count_increased_with_win_rate_not_down": true
    },
    "mid_weak": {
      "drawdown_improvement_pct": 0.0024,
      "ev_delta_pct": 0.117503,
      "passes_drawdown": false,
      "passes_material_ev": true,
      "passes_pnl": true,
      "passes_sharpe": true,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.054925,
      "sharpe_daily_delta": 0.16,
      "trade_count_increased_with_win_rate_not_down": true
    },
    "old_thin": {
      "drawdown_improvement_pct": 0.0,
      "ev_delta_pct": 0.00026,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.000214,
      "sharpe_daily_delta": 0.0,
      "trade_count_increased_with_win_rate_not_down": true
    }
  },
  "improves_vs_raw_form4": true,
  "material_vs_core": false,
  "no_core_ev_regression": true,
  "passed": false,
  "sample_guard_min_trades": 8,
  "sample_guard_passed": true,
  "single_owner_selected_event_trades": 8,
  "single_ticker_positive_share": 0.29,
  "single_ticker_positive_share_guard": "<= 0.50"
}
```

## Decision

Single-owner Form 4 forward-queue events improved the raw Form 4 overlay and were positive versus core, but the lift did not clear materiality. Keep Form 4 in forward observation rather than adding another paper promotion from the frozen sample.

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
  "promotion_blocker_if_positive": "A shared default-off Form 4 single-owner queue/paper adapter must be wired in run.py and replay before any trade-enabled promotion.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
