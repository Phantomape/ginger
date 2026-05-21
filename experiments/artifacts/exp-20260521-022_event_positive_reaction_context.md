# exp-20260521-022 Event Positive Reaction Context

Decision: `rejected_event_positive_reaction_context`

Alpha search. Tests whether selected event rows with `positive_excess_0_to_2pct` first reaction deserve a paper-notional scalar on top of the accepted event non-narrow state context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.4987 | +0.2353 | $169,679.71 | $172,388.27 | $+2,708.56 |
| mid_weak | 9.4589 | 9.6042 | +0.1453 | $190,704.43 | $192,083.74 | $+1,379.31 |
| old_thin | 1.4387 | 1.3339 | -0.1048 | $71,933.84 | $69,112.52 | $-2,821.32 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| positive_reaction_context_050 | no | no | yes | -0.3439 | $-1,266.56 | 1 | 2 | 0.0015 |
| positive_reaction_context_075 | no | no | yes | -0.1721 | $-633.28 | 1 | 2 | 0.0007 |
| positive_reaction_context_125 | no | no | yes | +0.1334 | $+633.27 | 2 | 1 | 0.0000 |
| positive_reaction_context_150 | no | no | yes | +0.2758 | $+1,266.55 | 2 | 1 | 0.0000 |

## Selection

```json
{
  "target_breadth_buckets": [
    "broad_breadth",
    "mixed_breadth",
    "thin_breadth"
  ],
  "target_by_window": {
    "late_strong": {
      "breadth_buckets": [
        "mixed_breadth"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "balanced_state_leadership"
      ],
      "tickers": [
        "INTC",
        "NFLX"
      ],
      "total_pnl": 8125.71,
      "trade_count": 2,
      "wins": 1
    },
    "mid_weak": {
      "breadth_buckets": [
        "broad_breadth",
        "thin_breadth"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_buckets": [
        "broad_rotation",
        "weak_index"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "GS",
        "JPM"
      ],
      "total_pnl": 4137.93,
      "trade_count": 2,
      "wins": 2
    },
    "old_thin": {
      "breadth_buckets": [
        "broad_breadth",
        "mixed_breadth"
      ],
      "sources": [
        "sec_governance_procedural"
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
        "GS"
      ],
      "total_pnl": -8463.92,
      "trade_count": 3,
      "wins": 2
    }
  },
  "target_field": "reaction_bucket",
  "target_max_single_positive_pnl_share": 0.4993,
  "target_scaled_total_pnl": 3799.72,
  "target_sources": [
    "sec_governance_procedural"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation",
    "narrow_cap_weight_leadership",
    "weak_index"
  ],
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "GS",
    "INTC",
    "JPM",
    "NFLX"
  ],
  "target_trade_count": 7,
  "target_value": "positive_excess_0_to_2pct",
  "target_win_rate": 0.7143,
  "target_windows_present": 3,
  "target_wins": 5
}
```

## Production Impact

Replay-only scout. No shared policy, production adapter, order path, or live behavior changed.

No JavaScript was used.
