# exp-20260517-010 Event Rotation-Surface Revalidation After Exp009

Decision: `promising_replay_only_rotation_surface_tilt`

Alpha search, replay-only. Revalidates whether `rotation_breakout_leadership` event rows still deserve higher bounded paper notional than the current 2.0x non-generic positive event-surface add-on after the accepted exp009 core allocation change.

## Best Variant Vs Current Lead

| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.9939 | 6.3077 | +0.3138 | $128,348.37 | $132,792.86 | $+4,444.49 |
| mid_weak | 2.8629 | 3.0800 | +0.2171 | $90,598.43 | $93,901.64 | $+3,303.21 |
| old_thin | 0.6645 | 0.6725 | +0.0080 | $42,325.56 | $42,565.76 | $+240.20 |

## Aggregate Gate

- EV delta vs current lead: +0.5389 (+5.66%)
- PnL delta vs current lead: $+7,987.90 (+3.06%)
- EV windows improved/regressed: 3/0
- Sample guard passed: `True`

## Selection

```json
{
  "event_trade_count": 27,
  "max_single_rotation_positive_pnl_share": 0.531,
  "non_generic_positive_trade_count": 16,
  "rotation_surface_by_source": {
    "sec_governance_procedural": {
      "total_pnl": 1329.21,
      "trade_count": 4,
      "win_rate": 0.75,
      "wins": 3
    },
    "sec_negative_reaction": {
      "total_pnl": 7122.74,
      "trade_count": 3,
      "win_rate": 1.0,
      "wins": 3
    }
  },
  "rotation_surface_by_window": {
    "late_strong": {
      "tickers": [
        "GS",
        "LITE"
      ],
      "total_pnl": 4444.49,
      "trade_count": 2,
      "wins": 1
    },
    "mid_weak": {
      "tickers": [
        "CRDO",
        "GE",
        "GS",
        "JPM"
      ],
      "total_pnl": 3767.26,
      "trade_count": 4,
      "wins": 4
    },
    "old_thin": {
      "tickers": [
        "GS"
      ],
      "total_pnl": 240.2,
      "trade_count": 1,
      "wins": 1
    }
  },
  "rotation_surface_total_pnl": 8451.95,
  "rotation_surface_trade_count": 7,
  "rotation_surface_win_rate": 0.8571,
  "rotation_surface_windows_present": 3,
  "rotation_surface_wins": 6
}
```

## Production Impact

Replay only. The default-off paper path is shared in `quant/event_sleeve_bundle.py`, and this run does not enable live/default orders. A live-capital version still needs closed forward replacement-value evidence and explicit enablement.
