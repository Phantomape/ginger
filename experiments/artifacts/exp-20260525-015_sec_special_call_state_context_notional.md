# exp-20260525-015 SEC Special-Call State-Context Notional

Decision: `rejected_sec_special_call_state_context_notional`.

Alpha search. Tests call/webcast SEC negative-reaction rows only when `state_bucket` is broad_rotation or weak_index.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.9351 | +0.6717 | $169,679.71 | $182,722.28 | $+13,042.57 |
| mid_weak | 9.4589 | 10.0676 | +0.6087 | $190,704.43 | $201,351.31 | $+10,646.88 |
| old_thin | 1.4387 | 1.4387 | +0.0000 | $71,933.84 | $71,933.84 | $+0.00 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| state_context_call_110 | no | no | yes | +0.5219 | $+9,475.78 | 2 | 0 | 0.0000 |
| state_context_call_125 | no | no | yes | +1.2804 | $+23,689.45 | 2 | 0 | 0.0000 |

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
        "webcast"
      ],
      "source_trade_count": 5,
      "tickers": [
        "LITE"
      ],
      "total_pnl": 65212.91,
      "trade_count": 1,
      "wins": 1
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
      "total_pnl": 58237.55,
      "trade_count": 3,
      "wins": 3
    },
    "old_thin": {
      "hit_categories": [],
      "source_trade_count": 3,
      "tickers": [],
      "total_pnl": 0,
      "trade_count": 0,
      "wins": 0
    }
  },
  "target_field": "special_call_state_context_flag",
  "target_hit_categories": [
    "conference call",
    "earnings call",
    "webcast"
  ],
  "target_max_single_positive_pnl_share": 0.5283,
  "target_scaled_total_pnl": 123450.46,
  "target_source": "sec_negative_reaction",
  "target_state_buckets": [
    "broad_rotation",
    "weak_index"
  ],
  "target_tickers": [
    "CRDO",
    "GS",
    "LITE",
    "MCD"
  ],
  "target_trade_count": 4,
  "target_win_rate": 1.0,
  "target_windows_present": 2,
  "target_wins": 4
}
```

## Production Impact

Replay-only default-off paper scout. No shared policy, production adapter, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
