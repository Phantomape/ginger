# Form 4 Cluster Satellite

- experiment_id: `exp-20260508-028`
- timestamp: `2026-05-08T18:15:24+00:00`
- decision: `rejected_positive_sample_not_material`

## Hypothesis

Clustered PIT-safe Form 4 meaningful open-market purchases may be a higher-quality standalone event alpha than the prior single >=500k purchase queue, because repeated or multi-owner buying is stronger semantic confirmation without adding noisy tickers.

## Three-Window Results

| Window | Baseline EV | Cluster EV | Delta EV | Baseline PnL | Cluster PnL | Event PnL | Trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.2255 | 0.1581 | $90,788.88 | $93,073.73 | $1,602.86 | 19 -> 20 | 78.95% -> 80.00% |
| mid_weak | 1.6195 | 1.6807 | 0.0612 | $59,540.63 | $60,896.60 | $1,126.29 | 21 -> 23 | 52.38% -> 52.17% |
| old_thin | 0.3583 | 0.3583 | 0.0 | $27,347.42 | $27,347.42 | $0.00 | 22 -> 22 | 40.91% -> 40.91% |

## Aggregate

```json
{
  "after_ev_sum": 6.2645,
  "after_pnl_sum": 181317.75,
  "aggregate_ev_delta": 0.2193,
  "aggregate_ev_delta_pct": 0.036277,
  "aggregate_pnl_delta": 3640.82,
  "aggregate_pnl_delta_pct": 0.020491,
  "baseline_ev_sum": 6.0452,
  "baseline_pnl_sum": 177676.93,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 2,
  "windows_pnl_regressed": 0
}
```

## Decision

Clustered Form 4 buying was directionally positive, but it did not clear materiality and sample/concentration guards strongly enough to justify another event sleeve promotion.

## Production Impact

{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "promotion_blocker_if_positive": "A shared default-off Form 4 cluster queue/paper adapter must be wired in run.py and replay before any trade-enabled promotion.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}

