# exp-20260521-015 Event SEC Negative Source Quality

Decision: `rejected_event_sec_negative_source_quality`

Alpha search. Tests whether SEC negative-reaction event rows deserve a source-level paper-notional scalar on top of the accepted exp-20260521-013 event adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.9157 | +0.6523 | $169,679.71 | $182,698.37 | $+13,018.66 |
| mid_weak | 9.4589 | 10.1535 | +0.6946 | $190,704.43 | $203,884.59 | $+13,180.16 |
| old_thin | 1.4387 | 1.4210 | -0.0177 | $71,933.84 | $71,769.19 | $-164.65 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| sec_negative_source_075 | no | no | yes | -1.5132 | $-26,034.14 | 1 | 2 | 0.0012 |
| sec_negative_source_090 | no | no | yes | -0.5837 | $-10,413.69 | 1 | 2 | 0.0004 |
| sec_negative_source_110 | no | no | yes | +0.5262 | $+10,413.69 | 2 | 1 | 0.0004 |
| sec_negative_source_125 | no | no | yes | +1.3292 | $+26,034.17 | 2 | 1 | 0.0012 |

## Selection

```json
{
  "target_by_window": {
    "late_strong": {
      "reaction_buckets": [
        "reaction_-2_to_0",
        "reaction_-5_to_-2"
      ],
      "semantic_subcategories": [
        ""
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "text_event_types": [
        "earnings_release_text"
      ],
      "tickers": [
        "DE",
        "ISRG",
        "LITE",
        "MCD"
      ],
      "total_pnl": 65093.32,
      "trade_count": 5,
      "wins": 4
    },
    "mid_weak": {
      "reaction_buckets": [
        "reaction_-2_to_0",
        "reaction_-5_to_-2"
      ],
      "semantic_subcategories": [
        ""
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation",
        "narrow_cap_weight_leadership",
        "weak_index"
      ],
      "text_event_types": [
        "earnings_release_text"
      ],
      "tickers": [
        "CRDO",
        "DIS",
        "GS",
        "MCD"
      ],
      "total_pnl": 70903.87,
      "trade_count": 6,
      "wins": 6
    },
    "old_thin": {
      "reaction_buckets": [
        "reaction_-2_to_0"
      ],
      "semantic_subcategories": [
        ""
      ],
      "state_buckets": [
        "balanced_risk_on"
      ],
      "text_event_types": [
        "earnings_release_text",
        "item_2_02_other_text"
      ],
      "tickers": [
        "GS",
        "MCD",
        "RTX"
      ],
      "total_pnl": -823.33,
      "trade_count": 3,
      "wins": 2
    }
  },
  "target_field": "source",
  "target_max_single_positive_pnl_share": 0.4639,
  "target_reaction_buckets": [
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_scaled_total_pnl": 135173.86,
  "target_semantic_subcategories": [
    ""
  ],
  "target_source": "sec_negative_reaction",
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation",
    "narrow_cap_weight_leadership",
    "weak_index"
  ],
  "target_text_event_types": [
    "earnings_release_text",
    "item_2_02_other_text"
  ],
  "target_tickers": [
    "CRDO",
    "DE",
    "DIS",
    "GS",
    "ISRG",
    "LITE",
    "MCD",
    "RTX"
  ],
  "target_trade_count": 14,
  "target_win_rate": 0.8571,
  "target_windows_present": 3,
  "target_wins": 12
}
```

## Production Impact

No shared policy, production adapter, run adapter, order path, source capacity, or core behavior changed.

No JavaScript was used.
