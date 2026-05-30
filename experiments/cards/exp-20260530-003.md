# Form 4 Ownership-Delta Forward Queue

- experiment_id: `exp-20260530-003`
- timestamp: `2026-05-30T01:11:07+00:00`
- decision: `rejected_positive_not_promotable`

## Hypothesis

PIT-safe Form 4 meaningful purchases where at least one insider increases reported beneficial ownership by 10% or more may be a cleaner free SEC candidate source than the raw meaningful-purchase queue.

## Three-Window Results

| Window | Core EV | Raw Form4 EV | Ownership EV | Delta vs raw | Delta vs core | Core PnL | Ownership PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.2886 | -0.0061 | 0.1258 | $117,072.92 | $119,651.33 | $1,660.86 | 18 -> 20 |
| mid_weak | 2.1402 | 2.2689 | 2.262 | -0.0069 | 0.1218 | $78,110.11 | $80,214.36 | $2,032.62 | 21 -> 24 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,674.07 | $6.11 | 22 -> 23 |

## Aggregate vs Raw Form4

```json
{
  "after_ev_sum": 8.1417,
  "after_pnl_sum": 239539.76,
  "aggregate_ev_delta": -0.013,
  "aggregate_ev_delta_pct": -0.001594,
  "aggregate_pnl_delta": -97.45,
  "aggregate_pnl_delta_pct": -0.000407,
  "before_ev_sum": 8.1547,
  "before_pnl_sum": 239637.21,
  "max_drawdown_drift": 0.0,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 2,
  "windows_pnl_improved": 1,
  "windows_pnl_regressed": 1
}
```

## Aggregate vs Core

```json
{
  "after_ev_sum": 8.1417,
  "after_pnl_sum": 239539.76,
  "aggregate_ev_delta": 0.2476,
  "aggregate_ev_delta_pct": 0.031365,
  "aggregate_pnl_delta": 4688.77,
  "aggregate_pnl_delta_pct": 0.019965,
  "before_ev_sum": 7.8941,
  "before_pnl_sum": 234850.99,
  "max_drawdown_drift": 0.0,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Gate

```json
{
  "drawdown_guard_passed": true,
  "failed_reasons": [
    "does_not_improve_raw_form4_queue",
    "not_material_vs_core",
    "target_sample_too_small",
    "positive_pnl_hhi_concentration"
  ],
  "improves_core_cleanly": true,
  "improves_vs_raw_form4": false,
  "material_vs_core": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "ownership_delta_selected_event_trades": 6,
  "passed": false,
  "positive_pnl_by_ticker": {
    "DIS": 194.27,
    "LLY": 517.87,
    "MU": 1466.59,
    "TSLA": 1666.23,
    "UNH": 6.11
  },
  "positive_pnl_hhi": 0.35286,
  "positive_pnl_hhi_guard": "<= 0.35",
  "sample_guard_passed": false,
  "single_ticker_positive_share": 0.432667,
  "single_ticker_positive_share_guard": "<= 0.50",
  "target_trade_count_min": 8,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ]
}
```

## Decision

The ownership-delta Form 4 slice was positive versus core, but it failed the full Gate 4 standard once raw Form 4 replacement value, materiality, window stability, sample, and concentration were considered.

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
  "promotion_blocker_if_positive": "A shared default-off Form 4 ownership-delta queue/paper adapter must be wired through production and replay before any trade-enabled use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```
