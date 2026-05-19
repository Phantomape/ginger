# exp-20260516-030 Event Rotation Negative-Reaction Source Tilt

Decision: `rejected_negative_reaction_rotation_source_tilt`

Alpha search, replay-only. Tests one source-quality allocation variable inside the exp028 default-off event rotation paper lead.

## Gate 4 Result

| Window | Baseline EV | Variant EV | Delta EV | Baseline PnL | Variant PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.2751 | 6.5997 | +0.3246 | $132,385.86 | $136,922.40 | $+4,536.54 |
| mid_weak | 3.0546 | 3.1814 | +0.1268 | $92,563.83 | $94,685.96 | $+2,122.13 |
| old_thin | 0.6069 | 0.6069 | +0.0000 | $40,190.25 | $40,190.25 | $+0.00 |

## Sweep

| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max winner share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| negative_reaction_source_325 | no | +0.1166 | $+1,664.66 | 2 | 0 | 3 | 2 | 0.5378 |
| negative_reaction_source_350 | no | +0.2245 | $+3,329.34 | 2 | 0 | 3 | 2 | 0.5439 |
| negative_reaction_source_400 | no | +0.4514 | $+6,658.67 | 2 | 0 | 3 | 2 | 0.554 |

## Selection

```json
{
  "max_single_rotation_positive_pnl_share": 0.554,
  "rotation_surface_scaled_total_pnl": 32478.59,
  "target_by_window": {
    "late_strong": {
      "tickers": [
        "LITE"
      ],
      "total_pnl": 4536.55,
      "trade_count": 1,
      "wins": 1
    },
    "mid_weak": {
      "tickers": [
        "CRDO",
        "GS"
      ],
      "total_pnl": 2586.19,
      "trade_count": 2,
      "wins": 2
    },
    "old_thin": {
      "tickers": [],
      "total_pnl": 0.0,
      "trade_count": 0,
      "wins": 0
    }
  },
  "target_scaled_total_pnl": 28490.96,
  "target_source": "sec_negative_reaction",
  "target_surface": "rotation_breakout_leadership",
  "target_tickers": [
    "CRDO",
    "GS",
    "LITE"
  ],
  "target_trade_count": 3,
  "target_unscaled_total_pnl": 7122.74,
  "target_win_rate": 1.0,
  "target_windows_present": 2,
  "target_wins": 3
}
```

## Production Impact

Replay only. Production and default backtest order paths are unchanged. A live/default version requires a shared trade-enabled event adapter, run/backtester parity tests, and closed forward replacement-value evidence.
