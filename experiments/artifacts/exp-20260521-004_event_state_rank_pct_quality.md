# exp-20260521-004 Event State-Rank Quality

Decision: `rejected_event_state_rank_pct_quality`

Alpha search, replay-only. Tests whether top-quartile state_rank_pct is a useful event-quality allocation field on top of the accepted default-off event broad-breadth adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.6390 | 6.8033 | +0.1643 | $137,454.00 | $139,985.71 | $+2,531.71 |
| mid_weak | 3.6218 | 3.8232 | +0.2014 | $102,311.72 | $105,322.81 | $+3,011.09 |
| old_thin | 0.6850 | 0.7122 | +0.0272 | $43,082.99 | $43,963.96 | $+880.97 |

## Sweep

| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| state_rank_pct_le_25_105 | no | +0.1302 | $+2,141.27 | 3 | 0 | 12 | 3 | 0.3989 |
| state_rank_pct_le_25_110 | no | +0.2612 | $+4,282.52 | 3 | 0 | 12 | 3 | 0.3989 |
| state_rank_pct_le_25_115 | no | +0.3929 | $+6,423.77 | 3 | 0 | 12 | 3 | 0.3989 |

## Selection

```json
{
  "target_by_window": {
    "late_strong": {
      "tickers": [
        "DE",
        "GS",
        "LITE"
      ],
      "total_pnl": 19409.79,
      "trade_count": 3,
      "wins": 1
    },
    "mid_weak": {
      "tickers": [
        "CRDO",
        "GE",
        "GS",
        "JPM",
        "MCD"
      ],
      "total_pnl": 24685.95,
      "trade_count": 7,
      "wins": 7
    },
    "old_thin": {
      "tickers": [
        "CRDO",
        "GS"
      ],
      "total_pnl": 6754.1,
      "trade_count": 2,
      "wins": 2
    }
  },
  "target_max_single_positive_pnl_share": 0.3989,
  "target_scaled_total_pnl": 50849.84,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_rank_pct_max": 0.25,
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "CRDO",
    "DE",
    "GE",
    "GS",
    "JPM",
    "LITE",
    "MCD"
  ],
  "target_trade_count": 12,
  "target_win_rate": 0.8333,
  "target_windows_present": 3,
  "target_wins": 10
}
```

## Production Impact

Replay only. No shared policy, adapter, production report, core behavior, or live/default order path changed.
