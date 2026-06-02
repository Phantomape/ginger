# Form 4 Pre-Event Underpriced Purchase

- experiment_id: `exp-20260602-031`
- timestamp: `2026-06-02T23:15:09+00:00`
- decision: `rejected_positive_not_promotable`

## Hypothesis

PIT-safe Form 4 meaningful purchase events may have better forward value when the ticker was underpriced versus SPY over the prior 20 trading days before the usable event date.

## Gate Questions

```json
{
  "1_alpha_hypothesis": "entry / candidate_pool: insider purchases are more informative when the market has recently underpriced the ticker versus SPY, creating a contrarian event-timing edge rather than another owner-role filter.",
  "2_history_check": {
    "exp-20260504-034": "Raw Form 4 event satellite was positive but not promoted.",
    "exp-20260512-017": "Prior Form 4 relative-strength confirmation used the opposite chasing direction and failed sample.",
    "exp-20260529-002": "Executive-role Form 4 qualifier positive vs core but not raw and too concentrated.",
    "exp-20260530-003": "Ownership-delta Form 4 qualifier positive vs core but not raw and too small/materiality failed.",
    "exp-20260530-011": "Multi-filer Form 4 forward queue did not create promotable evidence.",
    "exp-20260602-016": "Form4 + FINRA short-pressure consensus did not improve raw Form4 queue."
  },
  "3_single_causal_variable": "Only the event qualifier changes by adding pre-event 20d relative underpricing versus SPY; core strategy, Form4 threshold, event notional, capacity, hold period, LLM/news, ranking, sizing, and exits stay fixed.",
  "4_acceptance_standard": "docs/backtesting.md three fixed windows; must improve aggregate EV/PnL versus core and raw Form4, avoid window EV/PnL regressions, and pass drawdown, survival, target sample, and concentration guards.",
  "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260602_031_form4_pre_event_underpriced_purchase.py"
}
```

## Three-Window Results

| Window | Core EV | Raw Form4 EV | Qualified EV | Delta vs raw | Delta vs core | Core PnL | Qualified PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.2299 | -0.0648 | 0.0671 | $117,072.92 | $118,323.50 | $333.04 | 18 -> 20 |
| mid_weak | 2.1402 | 2.2689 | 2.1968 | -0.0721 | 0.0566 | $78,110.11 | $79,308.04 | $1,126.29 | 21 -> 23 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,667.96 | $0.00 | 22 -> 22 |

## Aggregate vs Raw Form4

```json
{
  "aggregate_ev_after": 8.0178,
  "aggregate_ev_before": 8.1547,
  "aggregate_ev_delta": -0.1369,
  "aggregate_ev_delta_pct": -0.016788,
  "aggregate_pnl_after": 237299.5,
  "aggregate_pnl_before": 239637.21,
  "aggregate_pnl_delta": -2337.71,
  "aggregate_pnl_delta_pct": -0.009755,
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
  "aggregate_ev_after": 8.0178,
  "aggregate_ev_before": 7.8941,
  "aggregate_ev_delta": 0.1237,
  "aggregate_ev_delta_pct": 0.01567,
  "aggregate_pnl_after": 237299.5,
  "aggregate_pnl_before": 234850.99,
  "aggregate_pnl_delta": 2448.51,
  "aggregate_pnl_delta_pct": 0.010426,
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
  "drawdown_guard_passed": true,
  "failed_reasons": [
    "does_not_improve_raw_form4_queue",
    "target_sample_too_small",
    "single_ticker_concentration",
    "positive_pnl_hhi_concentration"
  ],
  "improves_core_cleanly": true,
  "improves_vs_raw_form4": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "passed": false,
  "positive_pnl_by_ticker": {
    "LLY": 1277.77,
    "MSFT": 333.04
  },
  "positive_pnl_hhi": 0.671987,
  "positive_pnl_hhi_guard": "<= 0.6",
  "qualified_selected_event_trades": 4,
  "sample_guard_passed": false,
  "single_ticker_positive_share": 0.793247,
  "single_ticker_positive_share_guard": "<= 0.75",
  "target_trade_count_min": 8,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak"
  ]
}
```

## Decision

The underpriced Form 4 slice was positive versus the core baseline, but failed replacement value against raw Form 4 or failed one of the window, sample, drawdown, or concentration guards.

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
  "promotion_blocker_if_positive": "A shared default-off Form 4 underpriced-event paper adapter must be wired through production and replay with source-row caching and parity tests before any production report or order behavior can change.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```
