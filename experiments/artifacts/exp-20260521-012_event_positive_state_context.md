# exp-20260521-012 Event Positive-State Context

Decision: `accepted_default_off_event_positive_state_context`

Alpha search. Tests and promotes whether selected event rows with positive state-surface scores deserve a different paper-notional scalar on top of the accepted event adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.6053 | 7.9273 | +0.3220 | $155,210.79 | $162,778.78 | $+7,567.99 |
| mid_weak | 7.6013 | 8.5566 | +0.9553 | $160,365.48 | $175,699.37 | $+15,333.89 |
| old_thin | 1.1813 | 1.3030 | +0.1217 | $61,205.79 | $66,481.25 | $+5,275.46 |

## Sweep

| Variant | Passed | Sample Guard | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| positive_state_context_075 | no | yes | -1.5755 | $-28,177.36 | 0 | 3 | 18 | 3 | 0.2738 |
| positive_state_context_090 | no | yes | -0.6150 | $-11,270.95 | 0 | 3 | 18 | 3 | 0.2738 |
| positive_state_context_110 | no | yes | +0.5702 | $+11,270.94 | 3 | 0 | 18 | 3 | 0.2738 |
| positive_state_context_125 | yes | yes | +1.3990 | $+28,177.34 | 3 | 0 | 18 | 3 | 0.2738 |

## Selection

```json
{
  "target_breadth_buckets": [
    "broad_breadth",
    "mixed_breadth"
  ],
  "target_by_window": {
    "late_strong": {
      "breadth_buckets": [
        "mixed_breadth"
      ],
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "reaction_-2_to_0"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "AAPL",
        "DE",
        "GS",
        "LITE"
      ],
      "total_pnl": 37840.0,
      "trade_count": 4,
      "wins": 1
    },
    "mid_weak": {
      "breadth_buckets": [
        "broad_breadth",
        "mixed_breadth"
      ],
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
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "CRDO",
        "GE",
        "GS",
        "JPM",
        "MCD",
        "NOW"
      ],
      "total_pnl": 80149.88,
      "trade_count": 8,
      "wins": 7
    },
    "old_thin": {
      "breadth_buckets": [
        "broad_breadth",
        "mixed_breadth"
      ],
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct",
        "reaction_-2_to_0"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
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
      "total_pnl": 26377.38,
      "trade_count": 6,
      "wins": 4
    }
  },
  "target_field": "state_score_positive",
  "target_max_single_positive_pnl_share": 0.2738,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_scaled_total_pnl": 144367.26,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
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
    "JPM",
    "LITE",
    "MCD",
    "NOW",
    "RTX"
  ],
  "target_trade_count": 18,
  "target_value": true,
  "target_win_rate": 0.6667,
  "target_windows_present": 3,
  "target_wins": 12
}
```

## Production Impact

Shared default-off event adapter/reporting changed. Core behavior, source capacity, and live/default order paths are unchanged.

No JavaScript was used.
