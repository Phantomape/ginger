# exp-20260521-019 Event Attention Persistence

Decision: `rejected_event_attention_persistence`

Alpha search. Tests whether selected event rows with a prior same-ticker event in the last 60 calendar days deserve a paper-notional scalar on top of the accepted event non-narrow state context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.2634 | +0.0000 | $169,679.71 | $169,679.71 | $+0.00 |
| mid_weak | 9.4589 | 9.4589 | +0.0000 | $190,704.43 | $190,704.43 | $+0.00 |
| old_thin | 1.4387 | 1.4981 | +0.0594 | $71,933.84 | $73,800.24 | $+1,866.40 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| attention_persistence_075 | no | no | yes | +0.0594 | $+1,866.40 | 1 | 0 | 0.0000 |
| attention_persistence_090 | no | no | yes | +0.0222 | $+746.56 | 1 | 0 | 0.0000 |
| attention_persistence_110 | no | no | yes | -0.0292 | $-746.55 | 0 | 1 | 0.0000 |
| attention_persistence_125 | no | no | yes | -0.0654 | $-1,866.39 | 0 | 1 | 0.0000 |
| attention_persistence_150 | no | no | yes | -0.1292 | $-3,732.78 | 0 | 1 | 0.0000 |

## Selection

```json
{
  "lookback_days": 60,
  "target_by_window": {
    "late_strong": {
      "prior_day_gaps": [],
      "prior_sources": [],
      "reaction_buckets": [],
      "sources": [],
      "state_buckets": [],
      "state_surfaces": [],
      "tickers": [],
      "total_pnl": 0,
      "trade_count": 0,
      "wins": 0
    },
    "mid_weak": {
      "prior_day_gaps": [],
      "prior_sources": [],
      "reaction_buckets": [],
      "sources": [],
      "state_buckets": [],
      "state_surfaces": [],
      "tickers": [],
      "total_pnl": 0,
      "trade_count": 0,
      "wins": 0
    },
    "old_thin": {
      "prior_day_gaps": [
        21,
        35
      ],
      "prior_sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "reaction_buckets": [
        "positive_excess_0_to_2pct"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_buckets": [
        "broad_rotation",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "GS"
      ],
      "total_pnl": -5599.16,
      "trade_count": 2,
      "wins": 1
    }
  },
  "target_field": "attention_persistence_flag",
  "target_max_single_positive_pnl_share": 1.0,
  "target_prior_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_reaction_buckets": [
    "positive_excess_0_to_2pct"
  ],
  "target_scaled_total_pnl": -5599.16,
  "target_sources": [
    "sec_governance_procedural"
  ],
  "target_state_buckets": [
    "broad_rotation",
    "narrow_cap_weight_leadership"
  ],
  "target_state_surfaces": [
    "broad_breadth_trend_persistence",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "GS"
  ],
  "target_trade_count": 2,
  "target_win_rate": 0.5,
  "target_windows_present": 1,
  "target_wins": 1
}
```

## Production Impact

Replay-only scout. No shared policy, production adapter, order path, or live behavior changed.

No JavaScript was used.
