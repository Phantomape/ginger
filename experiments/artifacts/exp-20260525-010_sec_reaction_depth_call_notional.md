# exp-20260525-010 SEC Reaction-Depth Call Notional

Decision: `rejected_sec_reaction_depth_call_notional`.

Alpha search. Tests call/webcast SEC negative-reaction rows only when `reaction_bucket == reaction_-5_to_-2`.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.2642 | +0.0008 | $169,679.71 | $170,044.67 | $+364.96 |
| mid_weak | 9.4589 | 10.1866 | +0.7277 | $190,704.43 | $203,732.36 | $+13,027.93 |
| old_thin | 1.4387 | 1.4387 | +0.0000 | $71,933.84 | $71,933.84 | $+0.00 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| reaction_depth_call_105 | no | no | yes | +0.1352 | $+2,678.57 | 1 | 1 | 0.0000 |
| reaction_depth_call_110 | no | no | yes | +0.2878 | $+5,357.16 | 1 | 1 | 0.0000 |
| reaction_depth_call_125 | no | no | yes | +0.7285 | $+13,392.89 | 2 | 0 | 0.0000 |

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
        "ISRG"
      ],
      "total_pnl": 1824.77,
      "trade_count": 1,
      "wins": 1
    },
    "mid_weak": {
      "hit_categories": [
        "conference call",
        "webcast"
      ],
      "source_trade_count": 6,
      "tickers": [
        "CRDO"
      ],
      "total_pnl": 65139.75,
      "trade_count": 2,
      "wins": 2
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
  "target_field": "reaction_depth_call_flag",
  "target_hit_categories": [
    "conference call",
    "webcast"
  ],
  "target_max_single_positive_pnl_share": 0.8252,
  "target_reaction_bucket": "reaction_-5_to_-2",
  "target_scaled_total_pnl": 66964.52,
  "target_source": "sec_negative_reaction",
  "target_tickers": [
    "CRDO",
    "ISRG"
  ],
  "target_trade_count": 3,
  "target_win_rate": 1.0,
  "target_windows_present": 2,
  "target_wins": 3
}
```

## Production Impact

Replay-only default-off paper scout. No shared policy, production adapter, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
