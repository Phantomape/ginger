# exp-20260604-007 Broad-Market Prior-Lead Consensus

Decision: `rejected_broad_market_prior_lead_underperformed_accepted_comparator`.

Single causal variable: use `BROAD_MARKET_LEADERSHIP_PAPER` only when it led the same ticker by 1-3 trading days before an accepted consensus source key.

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
- Broad-market prior-lead confirmed target trades: `0`

## Timing Diagnostics

```json
{
  "late_strong": {
    "all_source_row_counts_after_merge": 178,
    "existing_source_key_count": 153,
    "prior_lead_confirmed_existing_key_count": 0,
    "prior_lead_lag_counts": {},
    "prior_lead_shifted_rows_added": 0,
    "raw_broad_source_key_count": 30,
    "same_date_overlap_with_existing_source_rows": 0
  },
  "mid_weak": {
    "all_source_row_counts_after_merge": 216,
    "existing_source_key_count": 181,
    "prior_lead_confirmed_existing_key_count": 0,
    "prior_lead_lag_counts": {},
    "prior_lead_shifted_rows_added": 0,
    "raw_broad_source_key_count": 30,
    "same_date_overlap_with_existing_source_rows": 0
  },
  "old_thin": {
    "all_source_row_counts_after_merge": 194,
    "existing_source_key_count": 163,
    "prior_lead_confirmed_existing_key_count": 0,
    "prior_lead_lag_counts": {},
    "prior_lead_shifted_rows_added": 0,
    "raw_broad_source_key_count": 30,
    "same_date_overlap_with_existing_source_rows": 0
  }
}
```

## Gate 4

```json
{
  "accepted_comparator": {
    "aggregate_expected_value_delta_vs_accepted": 0.0,
    "aggregate_total_pnl_delta_vs_accepted": 0.0,
    "ev_regression_windows_vs_accepted": [],
    "passed": false
  },
  "decision": "rejected_broad_market_prior_lead_underperformed_accepted_comparator",
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
  "parity_note": "This experiment changes no production code. A retained prior-lead source-timing construction would need the shared free-data consensus adapter to consume the same prior 1-3 trading-day BROAD_MARKET_LEADERSHIP_PAPER rows in both daily run and replay before any candidate queue or order surface could change.",
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
