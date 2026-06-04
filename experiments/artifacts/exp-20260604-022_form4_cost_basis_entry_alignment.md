# Form 4 Cost-Basis Entry Alignment

- experiment_id: `exp-20260604-022`
- timestamp: `2026-06-04T18:11:37+00:00`
- decision: `rejected_positive_not_promotable`

## Hypothesis

PIT-safe SEC Form 4 meaningful-purchase candidates may have cleaner replacement value when the execution-time entry open remains within 5% above the insider's disclosed weighted purchase cost basis.

## Three-Window Results

| Window | Core EV | Raw Form4 EV | Cost-Basis EV | Delta vs raw | Delta vs core | Core PnL | Cost-Basis PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.2451 | -0.0496 | 0.0823 | $117,072.92 | $118,399.05 | $408.59 | 18 -> 20 |
| mid_weak | 2.1402 | 2.2689 | 2.1589 | -0.11 | 0.0187 | $78,110.11 | $78,506.82 | $325.07 | 21 -> 24 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,674.07 | $6.11 | 22 -> 23 |

## Aggregate vs Raw Form4

```json
{
  "after_ev_sum": 7.9951,
  "after_pnl_sum": 236579.94,
  "aggregate_ev_delta": -0.1596,
  "aggregate_ev_delta_pct": -0.019572,
  "aggregate_pnl_delta": -3057.27,
  "aggregate_pnl_delta_pct": -0.012758,
  "before_ev_sum": 8.1547,
  "before_pnl_sum": 239637.21,
  "max_drawdown_drift": 0.0016,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 2,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 2
}
```

## Aggregate vs Core

```json
{
  "after_ev_sum": 7.9951,
  "after_pnl_sum": 236579.94,
  "aggregate_ev_delta": 0.101,
  "aggregate_ev_delta_pct": 0.012794,
  "aggregate_pnl_delta": 1728.95,
  "aggregate_pnl_delta_pct": 0.007362,
  "before_ev_sum": 7.8941,
  "before_pnl_sum": 234850.99,
  "max_drawdown_drift": 0.0001,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Gate

```json
{
  "cost_basis_selected_event_trades": 6,
  "drawdown_guard_passed": true,
  "failed_reasons": [
    "does_not_improve_raw_form4_queue",
    "not_material_vs_core",
    "target_sample_too_small",
    "single_ticker_concentration",
    "positive_pnl_hhi_concentration"
  ],
  "improves_core_cleanly": true,
  "improves_vs_raw_form4": false,
  "material_vs_core": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "passed": false,
  "positive_pnl_by_ticker": {
    "DIS": 194.27,
    "LLY": 1277.77,
    "MSFT": 214.32,
    "UNH": 6.11
  },
  "positive_pnl_hhi": 0.599209,
  "positive_pnl_hhi_guard": "<= 0.35",
  "sample_guard_passed": false,
  "single_ticker_positive_share": 0.754974,
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

Cost-basis entry alignment was positive versus core, but failed the full Gate 4 standard once raw Form 4 replacement value, materiality, window stability, sample, and concentration were considered.

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
  "promotion_blocker_if_positive": "A shared default-off Form 4 cost-basis queue/paper adapter must be wired through production and replay before any trade-enabled use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
