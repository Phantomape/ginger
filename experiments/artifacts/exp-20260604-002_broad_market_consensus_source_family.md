# exp-20260604-002 Broad-Market Consensus Source Family

Decision: `rejected_broad_market_consensus_source_family_underperformed_accepted_comparator`.

Single causal variable: add `BROAD_MARKET_LEADERSHIP_PAPER` as one independent source family to the accepted free-data consensus replay.

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Accepted EV | dEV vs Accepted | dPnL | dPnL vs Accepted | Targets |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.8860 | +0.7232 | 5.8860 | +0.0000 | $+7,368.07 | $+0.00 | 9 |
| mid_weak | 2.1402 | 2.4133 | +0.2731 | 2.4133 | +0.0000 | $+4,817.45 | $+0.00 | 22 |
| old_thin | 0.5911 | 0.9006 | +0.3095 | 0.9006 | +0.0000 | $+11,212.24 | $+0.00 | 16 |

## Aggregate

- EV delta vs core baseline: `1.3058`
- PnL delta vs core baseline: `$23,397.76`
- EV delta vs accepted comparator: `0.0`
- PnL delta vs accepted comparator: `$0.00`
- Target trades: `47`
- Broad-market confirmed target trades: `0`

## Gate 4

```json
{
  "accepted_comparator": {
    "aggregate_expected_value_delta_vs_accepted": 0.0,
    "aggregate_total_pnl_delta_vs_accepted": 0.0,
    "ev_regression_windows_vs_accepted": [],
    "passed": false
  },
  "decision": "rejected_broad_market_consensus_source_family_underperformed_accepted_comparator",
  "ev_windows_improved": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "gates": {
    "accepted_comparator_beaten": false,
    "aggregate_expected_value_positive": true,
    "aggregate_pnl_positive": true,
    "all_windows_expected_value_improved": true,
    "all_windows_pnl_improved": true,
    "concentration_guard_passed": true,
    "drawdown_drift_passed": true,
    "source_family_min_count_passed": true,
    "survival_floor_passed": true,
    "target_trade_count_passed": true,
    "target_window_count_passed": true
  },
  "max_drawdown_delta": -0.002,
  "min_survival_rate": 0.7925,
  "passed": false,
  "pnl_windows_improved": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "rationale": "The candidate improved versus the core baseline but failed the current accepted free-data consensus comparator from exp-20260603-014.",
  "requires_parity_before_promotion": false
}
```

## Production Impact

```json
{
  "adapter_status": "replay_only_no_live_adapter",
  "alters_orders": false,
  "backtester_adapter_changed": false,
  "parity_note": "This experiment changes no production code. A retained broad-market source-family lead would need the shared free-data consensus adapter to consume BROAD_MARKET_LEADERSHIP_PAPER source rows from the same broad_market_paper_sleeve.py path in both daily run and replay before any candidate queue or order surface could change.",
  "parity_test_added": false,
  "production_orders_changed": false,
  "production_watchlist_changed": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
