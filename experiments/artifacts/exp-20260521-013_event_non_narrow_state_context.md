# exp-20260521-013 Event Non-Narrow State Context

Decision: `accepted_default_off_event_non_narrow_state_context`

Alpha search. Tests whether event rows in non-narrow state buckets deserve a modest paper-notional scalar on top of the accepted event positive-state context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.9273 | 8.2634 | +0.3361 | $162,778.78 | $169,679.71 | $+6,900.93 |
| mid_weak | 8.5566 | 9.4589 | +0.9023 | $175,699.37 | $190,704.43 | $+15,005.06 |
| old_thin | 1.3030 | 1.4387 | +0.1357 | $66,481.25 | $71,933.84 | $+5,452.59 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| non_narrow_state_context_090 | no | yes | yes | -0.9560 | $-18,239.03 | 0 | 3 | 0.0023 |
| non_narrow_state_context_105 | no | yes | yes | +0.4704 | $+9,119.52 | 3 | 0 | 0.0067 |
| non_narrow_state_context_110 | no | yes | yes | +0.9265 | $+18,239.05 | 3 | 0 | 0.0133 |
| non_narrow_state_context_115 | yes | yes | yes | +1.3741 | $+27,358.58 | 3 | 0 | 0.0199 |
| non_narrow_state_context_120 | no | yes | no | +1.7999 | $+36,478.10 | 3 | 0 | 0.0264 |

## Selection

```json
{
  "excluded_state_bucket": "narrow_cap_weight_leadership",
  "target_breadth_buckets": [
    "broad_breadth",
    "mixed_breadth",
    "thin_breadth"
  ],
  "target_by_window": {
    "late_strong": {
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
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "state_surfaces": [
        "",
        "balanced_state_leadership",
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "AAPL",
        "DE",
        "GS",
        "INTC",
        "ISRG",
        "LITE",
        "MCD"
      ],
      "total_pnl": 52907.18,
      "trade_count": 8,
      "wins": 5
    },
    "mid_weak": {
      "breadth_buckets": [
        "broad_breadth",
        "mixed_breadth",
        "thin_breadth"
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
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation",
        "weak_index"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "CRDO",
        "GE",
        "GS",
        "JPM",
        "MCD",
        "TRIP"
      ],
      "total_pnl": 119041.15,
      "trade_count": 9,
      "wins": 9
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
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "mid_dispersion_selective_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "CRDO",
        "GS",
        "MCD",
        "RTX"
      ],
      "total_pnl": 41803.21,
      "trade_count": 6,
      "wins": 5
    }
  },
  "target_field": "state_bucket",
  "target_max_single_positive_pnl_share": 0.233,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_scaled_total_pnl": 213751.54,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation",
    "weak_index"
  ],
  "target_state_surfaces": [
    "",
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
    "INTC",
    "ISRG",
    "JPM",
    "LITE",
    "MCD",
    "RTX",
    "TRIP"
  ],
  "target_trade_count": 23,
  "target_values": [
    "balanced_risk_on",
    "broad_rotation",
    "weak_index"
  ],
  "target_win_rate": 0.8261,
  "target_windows_present": 3,
  "target_wins": 19
}
```

## Production Impact

Shared default-off event adapter/reporting changed. Core behavior, source capacity, and live/default order paths are unchanged.

No JavaScript was used.
