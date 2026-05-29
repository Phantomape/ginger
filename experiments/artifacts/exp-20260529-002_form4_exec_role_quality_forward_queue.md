# Form 4 Executive-Role Forward Queue

- experiment_id: `exp-20260529-002`
- timestamp: `2026-05-29T01:16:26+00:00`
- decision: `rejected_positive_sample_not_material`

## Hypothesis

PIT-safe Form 4 forward-queue events with a CEO, CFO, or president title may be a cleaner standalone insider-buying alpha than the raw meaningful purchase queue, because senior operating executives should have stronger information content than broad insider-role metadata.

## Three-Window Results

| Window | Core EV | Raw Form4 EV | Exec-role EV | Delta vs raw | Delta vs core | Core PnL | Exec-role PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.2204 | -0.0743 | 0.0576 | $117,072.92 | $118,109.18 | $118.72 | 18 -> 19 |
| mid_weak | 2.1402 | 2.2689 | 2.2241 | -0.0448 | 0.0839 | $78,110.11 | $80,002.11 | $1,820.36 | 21 -> 24 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,667.96 | $0.00 | 22 -> 22 |

## Aggregate vs Raw Form4

```json
{
  "after_ev_sum": 8.0356,
  "after_pnl_sum": 237779.25,
  "aggregate_ev_delta": -0.1191,
  "aggregate_ev_delta_pct": -0.014605,
  "aggregate_pnl_delta": -1857.96,
  "aggregate_pnl_delta_pct": -0.007753,
  "before_ev_sum": 8.1547,
  "before_pnl_sum": 239637.21,
  "max_drawdown_drift": 0.0016,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 2,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 3
}
```

## Aggregate vs Core

```json
{
  "after_ev_sum": 8.0356,
  "after_pnl_sum": 237779.25,
  "aggregate_ev_delta": 0.1415,
  "aggregate_ev_delta_pct": 0.017925,
  "aggregate_pnl_delta": 2928.26,
  "aggregate_pnl_delta_pct": 0.012469,
  "before_ev_sum": 7.8941,
  "before_pnl_sum": 234850.99,
  "max_drawdown_drift": 0.0001,
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
      "drawdown_improvement_pct": 0.0001,
      "ev_delta_pct": 0.011157,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.008851,
      "sharpe_daily_delta": 0.01,
      "trade_count_increased_with_win_rate_not_down": true
    },
    "mid_weak": {
      "drawdown_improvement_pct": -0.0001,
      "ev_delta_pct": 0.039202,
      "passes_drawdown": false,
      "passes_material_ev": false,
      "passes_pnl": false,
      "passes_sharpe": false,
      "passes_trade_count": true,
      "pnl_delta_pct": 0.024222,
      "sharpe_daily_delta": 0.04,
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
  "drawdown_guard_passed": true,
  "exec_role_selected_event_trades": 4,
  "improves_vs_raw_form4": false,
  "material_vs_core": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "no_core_ev_regression": true,
  "passed": false,
  "positive_pnl_by_ticker": {
    "LLY": 1277.77,
    "MSFT": 118.72,
    "TSLA": 694.07
  },
  "positive_pnl_hhi": 0.487027,
  "positive_pnl_hhi_guard": "<= 0.35",
  "sample_guard_min_trades": 8,
  "sample_guard_passed": false,
  "single_ticker_positive_share": 0.611209,
  "single_ticker_positive_share_guard": "<= 0.50"
}
```

## Decision

Executive-role Form 4 events were positive versus core, but the result did not clear all materiality, raw-queue improvement, drawdown, sample, and concentration gates. Keep Form 4 role quality in forward observation rather than promoting another frozen-window paper rule.

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "live_slots_changed": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "promotion_blocker_if_positive": "A shared default-off Form 4 executive-role queue/paper adapter must be wired in run.py and replay before any trade-enabled promotion.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```
