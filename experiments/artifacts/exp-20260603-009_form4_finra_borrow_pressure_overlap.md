# Form 4 FINRA Borrow-Pressure Overlap

- experiment_id: `exp-20260603-009`
- timestamp: `2026-06-03T08:13:07+00:00`
- decision: `rejected_form4_finra_borrow_pressure_overlap`

## Hypothesis

Raw PIT-safe Form 4 meaningful-purchase events may have cleaner candidate-pool replacement value when confirmed by the accepted official FINRA borrow-pressure admission rule.

## Gate Questions

```json
{
  "1_alpha_hypothesis": "candidate_pool / entry: meaningful insider buys may retain cleaner replacement value when the same ticker also has official FINRA borrow-pressure evidence. This follows the playbook preference for free, PIT-safe, production-visible candidate-pool data edges.",
  "2_history_check": {
    "exp-20260530-011": "Multi-filer Form 4 queue was not promotable; this run avoids another Form 4-only threshold by requiring independent FINRA confirmation.",
    "exp-20260602-016": "Older Form4+FINRA percentile-score consensus failed; this run uses the later accepted FINRA days-to-cover plus positive short interest change rule instead of retuning a score floor.",
    "exp-20260603-006": "FINRA borrow-pressure candidate admission improved all three windows and was accepted as a default-off paper source.",
    "exp-20260603-007": "Shared FINRA borrow-pressure adapter promotion changed no live orders and established the accepted borrow-pressure condition.",
    "exp-20260603-008": "Form 4 post-drawdown qualifier was positive vs core but failed raw Form 4 replacement and sample/window/concentration gates."
  },
  "3_single_causal_variable": "raw PIT-safe Form 4 forward events require latest published FINRA days-to-cover >= 3.0 and short-interest change pct > 0.0 on or before usable trade date",
  "4_acceptance_standard": "docs/backtesting.md three fixed windows; must improve aggregate EV/PnL versus core and raw Form 4, avoid window EV/PnL regressions, pass drawdown, survival, target sample, materiality, and concentration guards.",
  "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260603_009_form4_finra_borrow_pressure_overlap.py"
}
```

## Three-Window Results

| Window | Core EV | Raw Form4 EV | Overlap EV | Delta vs raw | Delta vs core | Core PnL | Overlap PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.1628 | -0.1319 | 0.0 | $117,072.92 | $117,072.92 | $0.00 | 18 -> 18 |
| mid_weak | 2.1402 | 2.2689 | 2.1402 | -0.1287 | 0.0 | $78,110.11 | $78,110.11 | $0.00 | 21 -> 21 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,667.96 | $0.00 | 22 -> 22 |

## Aggregate vs Raw Form4

```json
{
  "after_ev_sum": 7.8941,
  "after_pnl_sum": 234850.99,
  "aggregate_ev_delta": -0.2606,
  "aggregate_ev_delta_pct": -0.031957,
  "aggregate_pnl_delta": -4786.22,
  "aggregate_pnl_delta_pct": -0.019973,
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
  "after_ev_sum": 7.8941,
  "after_pnl_sum": 234850.99,
  "aggregate_ev_delta": 0.0,
  "aggregate_ev_delta_pct": 0.0,
  "aggregate_pnl_delta": 0.0,
  "aggregate_pnl_delta_pct": 0.0,
  "before_ev_sum": 7.8941,
  "before_pnl_sum": 234850.99,
  "max_drawdown_drift": 0.0,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 0
}
```

## Gate

```json
{
  "drawdown_guard_passed": true,
  "failed_reasons": [
    "does_not_improve_core_cleanly",
    "does_not_improve_raw_form4_queue",
    "not_material_vs_core",
    "target_sample_too_small",
    "target_window_coverage_too_small"
  ],
  "finra_consensus_selected_event_trades": 0,
  "improves_core_cleanly": false,
  "improves_vs_raw_form4": false,
  "material_vs_core": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "passed": false,
  "positive_pnl_by_ticker": {},
  "positive_pnl_hhi": null,
  "positive_pnl_hhi_guard": "<= 0.35",
  "sample_guard_passed": false,
  "single_ticker_positive_share": null,
  "single_ticker_positive_share_guard": "<= 0.5",
  "target_trade_count_min": 8,
  "target_window_count_min": 3,
  "target_windows": []
}
```

## Decision

The accepted FINRA borrow-pressure overlap did not produce positive, stable three-window EV/PnL evidence versus the core baseline.

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "live_slots_changed": false,
  "parity_test_added": false,
  "production_orders_changed": false,
  "production_signal_path_changed": false,
  "production_watchlist_changed": false,
  "promotion_blocker_if_positive": "A shared default-off Form 4 + accepted FINRA borrow-pressure adapter must be wired through production and replay with parity tests before any production report, watchlist, or order behavior can change.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
