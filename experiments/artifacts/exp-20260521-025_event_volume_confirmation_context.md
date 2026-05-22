# exp-20260521-025 Event Volume Confirmation Context

Decision: `rejected_event_volume_confirmation_context`

Alpha search. Tests whether selected event rows with `state_features.volume_ratio_20 >= 1.10` deserve a paper-notional scalar on top of the accepted event non-narrow state context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.6200 | +0.3566 | $169,679.71 | $179,584.01 | $+9,904.30 |
| mid_weak | 9.4589 | 10.2370 | +0.7781 | $190,704.43 | $205,151.29 | $+14,446.86 |
| old_thin | 1.4387 | 1.6216 | +0.1829 | $71,933.84 | $79,880.14 | $+7,946.30 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| volume_confirmation_105 | no | yes | yes | +0.3319 | $+8,074.36 | 3 | 0 | 0.0074 |
| volume_confirmation_110 | no | yes | yes | +0.6737 | $+16,148.74 | 3 | 0 | 0.0148 |
| volume_confirmation_115 | no | yes | no | +0.9858 | $+24,223.12 | 3 | 0 | 0.0221 |
| volume_confirmation_120 | no | yes | no | +1.3176 | $+32,297.46 | 3 | 0 | 0.0293 |

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
        "DE",
        "GS",
        "ISRG",
        "LITE",
        "MCD"
      ],
      "total_pnl": 59425.91,
      "trade_count": 5,
      "wins": 3
    },
    "mid_weak": {
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
        "broad_rotation",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "CRDO",
        "DIS",
        "GS",
        "TRIP"
      ],
      "total_pnl": 91484.15,
      "trade_count": 5,
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
        "balanced_risk_on"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "mid_dispersion_selective_leadership"
      ],
      "tickers": [
        "CRDO",
        "GS",
        "MCD",
        "RTX"
      ],
      "total_pnl": 47677.79,
      "trade_count": 5,
      "wins": 4
    }
  },
  "target_field": "volume_ratio_20",
  "target_max_single_positive_pnl_share": 0.3044,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_rule": "volume_ratio_20 >= 1.1",
  "target_scaled_total_pnl": 198587.85,
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
    "CRDO",
    "DE",
    "DIS",
    "GS",
    "ISRG",
    "LITE",
    "MCD",
    "RTX",
    "TRIP"
  ],
  "target_trade_count": 15,
  "target_win_rate": 0.8,
  "target_windows_present": 3,
  "target_wins": 12
}
```

## Production Impact

Shared default-off event adapter/reporting changed only if the Gate 4 decision is accepted. Core behavior, source capacity, and live/default order paths are unchanged.

No JavaScript was used.
