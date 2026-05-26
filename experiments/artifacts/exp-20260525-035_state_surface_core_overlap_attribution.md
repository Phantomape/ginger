# exp-20260525-035 State-Surface Paper Sleeve Core-Overlap Attribution

Decision: `state_surface_core_overlap_attribution_complete`.

Read-only `measurement_repair`. Quantifies the share of accepted
default-off state-surface paper PnL (latest accepted increment `exp-20260520-001`) that overlaps with same-window core entries.

## Gate 1 Core Replay Verification

```json
{
  "baseline_artifact": "data/experiments/exp-20260517-009/ample_slot_stock_rank1_topup.json",
  "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
  "by_window": {
    "late_strong": {
      "expected_value_score": 5.1628,
      "max_drawdown_pct": 0.0665,
      "sharpe_daily": 4.41,
      "signals_generated": 51,
      "signals_survived": 41,
      "survival_rate": 0.8039,
      "total_pnl": 117072.92,
      "total_return_pct": 1.1707,
      "trade_count": 18,
      "win_rate": 0.8333
    },
    "mid_weak": {
      "expected_value_score": 2.1402,
      "max_drawdown_pct": 0.1119,
      "sharpe_daily": 2.74,
      "signals_generated": 53,
      "signals_survived": 42,
      "survival_rate": 0.7925,
      "total_pnl": 78110.11,
      "total_return_pct": 0.7811,
      "trade_count": 21,
      "win_rate": 0.5238
    },
    "old_thin": {
      "expected_value_score": 0.5911,
      "max_drawdown_pct": 0.1001,
      "sharpe_daily": 1.49,
      "signals_generated": 60,
      "signals_survived": 52,
      "survival_rate": 0.8667,
      "total_pnl": 39667.96,
      "total_return_pct": 0.3967,
      "trade_count": 22,
      "win_rate": 0.4091
    }
  },
  "canonical_accepted_aggregate_expected_value_score_sum": 7.8941,
  "canonical_accepted_aggregate_total_pnl_sum": 234850.99,
  "ev_tolerance": 0.01,
  "expected_value_score_drift": 0.0,
  "observed_aggregate_expected_value_score_sum": 7.8941,
  "observed_aggregate_total_pnl_sum": 234850.99,
  "observed_aggregate_trade_count_sum": 61,
  "passed": true,
  "pnl_tolerance": 50.0,
  "total_pnl_drift": 0.0
}
```

## Aggregate Overlap Across Three Windows

| Lookback (TD) | Paper Trades w/ Overlap | Paper Trades w/o Overlap | PnL from Overlap | PnL from Non-Overlap | Overlap PnL Share | Positive PnL Overlap Share |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 23 | $8,434.72 | $156,136.22 | 5.13% | 4.96% |
| 3 | 7 | 17 | $34,942.07 | $129,628.87 | 21.23% | 21.96% |
| 5 | 13 | 11 | $59,674.27 | $104,896.67 | 36.26% | 36.49% |

## Per-Window Summary

| Window | Paper Trades | Core Trades | Paper PnL | N=0 Overlap Trades | N=0 Overlap PnL | N=3 Overlap Trades | N=3 Overlap PnL | N=5 Overlap Trades | N=5 Overlap PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 9 | 18 | $31,755.45 | 1 | $8,434.72 | 3 | $25,656.31 | 6 | $34,829.30 |
| mid_weak | 12 | 21 | $79,860.11 | 0 | $0.00 | 3 | $6,587.11 | 6 | $22,146.32 |
| old_thin | 3 | 22 | $52,955.38 | 0 | $0.00 | 1 | $2,698.65 | 1 | $2,698.65 |

## Next-Step Decision

```json
{
  "decision_thresholds": {
    "majority_overlap_min_share": 0.5,
    "mixed_overlap_min_share": 0.2
  },
  "downstream_gate4_requirement_if_promoted": "state_surface tightened Gate 4 requires aggregate EV improvement > 10%",
  "next_step_bucket": "mixed_overlap_with_core",
  "next_step_recommendation": "no immediate allocation gate. Collect closed forward replacement-value rows; revisit only with a materially new production-visible discriminator.",
  "pnl_from_core_overlap_share_n5": 0.362605
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
