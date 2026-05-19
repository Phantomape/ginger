# Form 4 Cluster Pre-Entry RS

- experiment_id: `exp-20260512-017`
- timestamp: `2026-05-12T08:39:31+00:00`
- decision: `rejected_positive_sample_not_material`

## Hypothesis

Clustered PIT-safe Form 4 meaningful open-market purchases whose ticker outperformed SPY during the last complete session before the usable entry may be a higher-quality standalone event alpha than raw clustered Form 4 buying, because price confirmation can separate informed accumulation from stale insider signals without adding noisy tickers.

## Three-Window Results

| Window | Baseline EV | Confirmed EV | Delta EV | Baseline PnL | Confirmed PnL | Event PnL | Trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.234 | 4.2995 | 0.0655 | $94,086.91 | $95,331.63 | $530.57 | 19 -> 20 | 78.95% -> 80.00% |
| mid_weak | 1.6689 | 1.7189 | 0.05 | $61,813.40 | $62,965.08 | $894.60 | 21 -> 23 | 52.38% -> 52.17% |
| old_thin | 0.3853 | 0.3853 | 0.0 | $28,544.11 | $28,544.11 | $0.00 | 22 -> 22 | 40.91% -> 40.91% |

## Aggregate

```json
{
  "after_ev_sum": 6.4037,
  "after_pnl_sum": 186840.82,
  "aggregate_ev_delta": 0.1155,
  "aggregate_ev_delta_pct": 0.018368,
  "aggregate_pnl_delta": 2396.4,
  "aggregate_pnl_delta_pct": 0.012993,
  "baseline_ev_sum": 6.2882,
  "baseline_pnl_sum": 184444.42,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 2,
  "windows_pnl_regressed": 0
}
```

## Decision

Clustered Form 4 buying with pre-entry relative-strength confirmation was directionally positive, but it did not clear materiality and sample/concentration guards strongly enough to justify another event sleeve promotion.

## Production Impact

{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "promotion_blocker_if_positive": "A shared default-off Form 4 pre-entry RS queue/paper adapter must be wired in run.py and replay before any trade-enabled promotion.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}

