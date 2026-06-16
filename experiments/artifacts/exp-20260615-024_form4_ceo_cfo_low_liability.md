# Form 4 CEO/CFO Low-Liability Confirmation

- experiment_id: `exp-20260615-024`
- timestamp: `2026-06-15T19:15:49+00:00`
- decision: `rejected_no_alpha`
- status: `rejected`

## Hypothesis

PIT SEC Form 4 CEO/CFO/President non-plan open-market purchases, when paired with already-known SEC Companyfacts low-liability confirmation, may isolate informed insider demand with better replacement value than broad clustered or owner-conviction Form 4 buys.

## Three-Window Results

| Window | Core EV | Role-only EV | After EV | Delta vs core | Delta vs role | Core PnL | After PnL | Event PnL | Events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.9685 | 5.0221 | -0.1407 | 0.0536 | $117,072.92 | $116,521.34 | $-1,469.12 | 7 |
| mid_weak | 2.1402 | 2.1981 | 2.1063 | -0.0339 | -0.0918 | $78,110.11 | $77,722.45 | $-459.31 | 5 |
| old_thin | 0.5911 | 0.5522 | 0.5769 | -0.0142 | 0.0247 | $39,667.96 | $39,245.80 | $-731.13 | 3 |

## Aggregate vs Core

```json
{
  "after_ev_sum": 7.7053,
  "after_pnl_sum": 233489.59,
  "after_trade_count": 76,
  "aggregate_ev_delta": -0.1888,
  "aggregate_ev_delta_pct": -0.023917,
  "aggregate_pnl_delta": -1361.4,
  "aggregate_pnl_delta_pct": -0.005797,
  "before_ev_sum": 7.8941,
  "before_pnl_sum": 234850.99,
  "before_trade_count": 61,
  "event_trade_count": 15,
  "max_drawdown_drift": 0.0017,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 3,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 3
}
```

## Aggregate vs Role-Only

```json
{
  "after_ev_sum": 7.7053,
  "after_pnl_sum": 233489.59,
  "after_trade_count": 76,
  "aggregate_ev_delta": -0.0135,
  "aggregate_ev_delta_pct": -0.001749,
  "aggregate_pnl_delta": -306.25,
  "aggregate_pnl_delta_pct": -0.00131,
  "before_ev_sum": 7.7188,
  "before_pnl_sum": 233795.84,
  "before_trade_count": 94,
  "event_trade_count": 15,
  "max_drawdown_drift": 0.003,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 2,
  "windows_pnl_regressed": 1
}
```

## Gate

```json
{
  "drawdown_guard_passed": true,
  "failed_reasons": [
    "does_not_improve_core_cleanly",
    "does_not_improve_role_only_comparator",
    "not_material_vs_core"
  ],
  "improves_core_cleanly": false,
  "improves_role_only_comparator": false,
  "material_vs_core": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "passed_replay_lead": false,
  "positive_pnl_by_ticker": {
    "CR": 551.9,
    "EPAM": 230.19,
    "GME": 891.67,
    "HL": 418.61,
    "MSTR": 304.8,
    "ROIV": 617.17
  },
  "positive_pnl_hhi": 0.198288,
  "positive_pnl_hhi_guard": "<= 0.35",
  "sample_guard_passed": true,
  "selected_event_trades": 15,
  "single_ticker_positive_share": 0.295809,
  "single_ticker_positive_share_guard": "<= 0.50",
  "target_trade_count_min": 8,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ]
}
```

## Decision

The bundle did not improve aggregate EV/PnL against the core baseline under the canonical three-window replay.

## Post-Run Reflection

- why_result_happened: The role/fundamental bundle was not enough to overcome the broad Form 4 failure pattern. Either executive open-market buys remain mostly reactive, or low liabilities/assets overlaps already accepted Companyfacts quality without adding enough event timing value.
- forbidden_near_neighbor_retry: Do not retune CEO/CFO/President title parsing, liabilities/assets threshold, purchase value floor, hold days, notional, capacity, or sort order on this archive.
- new_evidence_required: A valid retry needs forward closed paper outcomes or a genuinely new evidence source such as buy-size relative to executive compensation/holdings from a shared daily surface.

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "daily_snapshot_changed": false,
  "parity_test_added": false,
  "production_consistency_read": "No live/default production surface changed. A positive replay result is only a lead until this exact bundle is moved to a shared default-off helper used by historical replay and daily paper snapshots with parity tests.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
