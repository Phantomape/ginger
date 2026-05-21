# exp-20260521-024 Event Benchmark Momentum Context

Decision: `rejected_event_benchmark_momentum_context`

Alpha search. Tests whether selected event rows with positive 20-day excess return versus SPY deserve a paper-notional scalar on top of the accepted event non-narrow state context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.6159 | +0.3525 | $169,679.71 | $181,006.49 | $+11,326.78 |
| mid_weak | 9.4589 | 10.6632 | +1.2043 | $190,704.43 | $213,263.06 | $+22,558.63 |
| old_thin | 1.4387 | 1.5975 | +0.1588 | $71,933.84 | $79,874.97 | $+7,941.13 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| benchmark_momentum_105 | no | yes | yes | +0.3705 | $+8,365.29 | 3 | 0 | 0.0074 |
| benchmark_momentum_110 | no | yes | yes | +0.7220 | $+16,730.63 | 3 | 0 | 0.0148 |
| benchmark_momentum_115 | no | yes | no | +1.0531 | $+25,095.95 | 3 | 0 | 0.0220 |
| benchmark_momentum_120 | no | yes | no | +1.4040 | $+33,461.23 | 3 | 0 | 0.0292 |
| benchmark_momentum_125 | no | yes | no | +1.7156 | $+41,826.54 | 3 | 0 | 0.0363 |

## Selection

```json
{
  "rows_with_field_count": 26,
  "target_by_window": {
    "late_strong": {
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "reaction_-2_to_0",
        "reaction_-5_to_-2"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "AAPL",
        "DE",
        "GS",
        "ISRG",
        "LITE",
        "MCD"
      ],
      "total_pnl": 56633.91,
      "trade_count": 6,
      "wins": 3
    },
    "mid_weak": {
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct",
        "reaction_-2_to_0",
        "reaction_-5_to_-2"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "CRDO",
        "GE",
        "GS",
        "JPM",
        "NOW"
      ],
      "total_pnl": 112793.25,
      "trade_count": 6,
      "wins": 5
    },
    "old_thin": {
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct",
        "reaction_-2_to_0"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "mid_dispersion_selective_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "CRDO",
        "GS",
        "RTX"
      ],
      "total_pnl": 39705.73,
      "trade_count": 6,
      "wins": 4
    }
  },
  "target_field": "ret20_excess_spy",
  "target_max_single_positive_pnl_share": 0.2747,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_rule": "ret20_excess_spy > 0.0",
  "target_scaled_total_pnl": 209132.89,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation",
    "narrow_cap_weight_leadership"
  ],
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "mid_dispersion_selective_leadership",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "AAPL",
    "CRDO",
    "DE",
    "GE",
    "GS",
    "ISRG",
    "JPM",
    "LITE",
    "MCD",
    "NOW",
    "RTX"
  ],
  "target_trade_count": 18,
  "target_win_rate": 0.6667,
  "target_windows_present": 3,
  "target_wins": 12
}
```

## Production Impact

Shared default-off event adapter/reporting changed only if the Gate 4 decision is accepted. Core behavior, source capacity, and live/default order paths are unchanged.

No JavaScript was used.
