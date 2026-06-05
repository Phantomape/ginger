# Form 4 Purchase Liquidity Intensity

- experiment_id: `exp-20260605-001`
- timestamp: `2026-06-05T00:13:18+00:00`
- decision: `rejected_positive_not_promotable`

## Hypothesis

PIT-safe Form 4 meaningful purchases whose total insider purchase value is unusually large relative to the issuer's pre-event 20-day dollar volume may create a cleaner free-data candidate-pool overlay than the raw Form 4 queue.

## Three-Window Results

| Window | Core EV | Raw Form4 EV | Liquidity EV | Delta vs raw | Delta vs core | Core PnL | Liquidity PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.1628 | -0.1319 | 0.0 | $117,072.92 | $117,072.92 | $0.00 | 18 -> 18 |
| mid_weak | 2.1402 | 2.2689 | 2.1691 | -0.0998 | 0.0289 | $78,110.11 | $78,875.82 | $694.07 | 21 -> 22 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,667.96 | $0.00 | 22 -> 22 |

## Aggregate vs Raw Form4

```json
{
  "after_ev_sum": 7.923,
  "after_pnl_sum": 235616.7,
  "aggregate_ev_delta": -0.2317,
  "aggregate_ev_delta_pct": -0.028413,
  "aggregate_pnl_delta": -4020.51,
  "aggregate_pnl_delta_pct": -0.016777,
  "before_ev_sum": 8.1547,
  "before_pnl_sum": 239637.21,
  "max_drawdown_drift": 0.0015,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 2,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 3
}
```

## Aggregate vs Core

```json
{
  "after_ev_sum": 7.923,
  "after_pnl_sum": 235616.7,
  "aggregate_ev_delta": 0.0289,
  "aggregate_ev_delta_pct": 0.003661,
  "aggregate_pnl_delta": 765.71,
  "aggregate_pnl_delta_pct": 0.00326,
  "before_ev_sum": 7.8941,
  "before_pnl_sum": 234850.99,
  "max_drawdown_drift": 0.0,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 1,
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
    "target_window_coverage_too_small",
    "single_ticker_concentration",
    "positive_pnl_hhi_concentration"
  ],
  "improves_core_cleanly": true,
  "improves_vs_raw_form4": false,
  "liquidity_intensity_selected_event_trades": 1,
  "material_vs_core": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "passed": false,
  "positive_pnl_by_ticker": {
    "TSLA": 694.07
  },
  "positive_pnl_hhi": 1.0,
  "positive_pnl_hhi_guard": "<= 0.35",
  "sample_guard_passed": false,
  "single_ticker_positive_share": 1.0,
  "single_ticker_positive_share_guard": "<= 0.50",
  "target_trade_count_min": 8,
  "target_window_count_min": 3,
  "target_windows": [
    "mid_weak"
  ]
}
```

## Decision

The liquidity-normalized Form 4 slice was positive versus core, but it failed the full Gate 4 standard once raw Form 4 replacement value, materiality, window stability, sample, and concentration were considered.

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
  "promotion_blocker_if_positive": "A shared default-off Form 4 liquidity-intensity queue/paper adapter must be wired through production and replay before any trade-enabled use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
