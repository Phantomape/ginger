# exp-20260520-043 Event-Rotation Front-Rank Quality Tilt

Decision: `promising_replay_only_front_rank_event_rotation_quality_tilt`

Alpha search, replay-only. Tests whether top-quintile `state_rank_pct` event-rotation rows deserve extra paper notional on top of the 3.0x event-rotation baseline.

## Gate 4 Result

| Window | Baseline EV | Variant EV | Delta EV | Baseline PnL | Variant PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.3077 | 6.6330 | +0.3253 | $132,792.86 | $137,329.40 | $+4,536.54 |
| mid_weak | 3.0800 | 3.3020 | +0.2220 | $93,901.64 | $97,402.83 | $+3,501.19 |
| old_thin | 0.6725 | 0.6725 | +0.0000 | $42,565.76 | $42,565.76 | $+0.00 |

## Sweep

| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Target max share | Rotation max share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| front_rank_rotation_325 | no | +0.1282 | $+2,009.43 | 2 | 0 | 3 | 2 | 0.5644 | 0.5334 |
| front_rank_rotation_350 | no | +0.2669 | $+4,018.87 | 2 | 0 | 3 | 2 | 0.5644 | 0.5355 |
| front_rank_rotation_400 | yes | +0.5473 | $+8,037.73 | 2 | 0 | 3 | 2 | 0.5644 | 0.5389 |

## Selection

```json
{
  "front_rank_max_pct": 0.2,
  "rotation_max_single_positive_pnl_share": 0.5389,
  "rotation_surface_scaled_total_pnl": 33393.6,
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
        "GE"
      ],
      "total_pnl": 3501.2,
      "trade_count": 2,
      "wins": 2
    },
    "old_thin": {
      "tickers": [],
      "total_pnl": 0,
      "trade_count": 0,
      "wins": 0
    }
  },
  "target_max_single_positive_pnl_share": 0.5644,
  "target_scaled_total_pnl": 32151.0,
  "target_surface": "rotation_breakout_leadership",
  "target_tickers": [
    "CRDO",
    "GE",
    "LITE"
  ],
  "target_trade_count": 3,
  "target_unscaled_total_pnl": 8037.75,
  "target_win_rate": 1.0,
  "target_windows_present": 2,
  "target_wins": 3
}
```

## Production Impact

Replay only. Core backtest behavior and production order paths are unchanged. A live/default version would require shared adapter parity plus closed forward replacement-value evidence.
