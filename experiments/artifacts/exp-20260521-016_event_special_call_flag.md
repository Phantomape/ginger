# exp-20260521-016 Event Special Call Flag

Decision: `rejected_event_special_call_flag`

Alpha search. Tests whether sec_negative_reaction rows with explicit conference-call / webcast disclosure deserve a paper-notional scalar on top of the accepted event non-narrow state context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.9157 | +0.6523 | $169,679.71 | $182,698.37 | $+13,018.66 |
| mid_weak | 9.4589 | 10.1479 | +0.6890 | $190,704.43 | $203,773.67 | $+13,069.24 |
| old_thin | 1.4387 | 1.4210 | -0.0177 | $71,933.84 | $71,769.19 | $-164.65 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| special_call_105 | no | yes | yes | +0.2679 | $+5,184.66 | 2 | 1 | 0.0002 |
| special_call_110 | no | yes | yes | +0.5240 | $+10,369.33 | 2 | 1 | 0.0004 |
| special_call_115 | no | yes | yes | +0.8177 | $+15,553.98 | 2 | 1 | 0.0007 |
| special_call_120 | no | yes | yes | +1.0743 | $+20,738.60 | 2 | 1 | 0.0009 |
| special_call_125 | no | yes | yes | +1.3236 | $+25,923.25 | 2 | 1 | 0.0012 |

## Selection

```json
{
  "source_text_join_count": 14,
  "source_trade_count": 14,
  "special_call_patterns": [
    "conference call",
    "webcast",
    "fireside chat",
    "investor presentation",
    "question and answer",
    "q&a",
    "earnings call",
    "management will hold"
  ],
  "target_by_window": {
    "late_strong": {
      "hit_categories": [
        "conference call",
        "earnings call",
        "webcast"
      ],
      "source_trade_count": 5,
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
      "hit_categories": [
        "conference call",
        "earnings call",
        "webcast"
      ],
      "source_trade_count": 6,
      "tickers": [
        "CRDO",
        "GS",
        "MCD"
      ],
      "total_pnl": 70349.27,
      "trade_count": 5,
      "wins": 5
    },
    "old_thin": {
      "hit_categories": [
        "conference call",
        "earnings call",
        "webcast"
      ],
      "source_trade_count": 3,
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
  "target_field": "special_call_flag",
  "target_hit_categories": [
    "conference call",
    "earnings call",
    "webcast"
  ],
  "target_max_single_positive_pnl_share": 0.4657,
  "target_scaled_total_pnl": 134619.26,
  "target_source": "sec_negative_reaction",
  "target_tickers": [
    "CRDO",
    "DE",
    "GS",
    "ISRG",
    "LITE",
    "MCD",
    "RTX"
  ],
  "target_trade_count": 13,
  "target_win_rate": 0.8462,
  "target_windows_present": 3,
  "target_wins": 11
}
```

## Production Impact

Replay-only scout. No shared policy, production adapter, order path, or live behavior changed.

No JavaScript was used.
