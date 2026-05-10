# exp-20260510-001 Event Rotation-Surface Tilt

Decision: `promising_replay_only_rotation_surface_tilt`

Alpha search. Tests whether `rotation_breakout_leadership` event rows deserve a higher bounded paper notional than the current 2.0x non-generic positive event-surface add-on.

## Best Variant Vs Current Lead

| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.8980 | 5.2074 | +0.3094 | $101,828.78 | $106,273.27 | $+4,444.49 |
| mid_weak | 2.3533 | 2.5742 | +0.2209 | $72,186.99 | $75,490.20 | $+3,303.21 |
| old_thin | 0.4231 | 0.4295 | +0.0064 | $30,005.02 | $30,245.22 | $+240.20 |

## Aggregate Gate

- EV delta vs current lead: +0.5367 (+6.99%)
- PnL delta vs current lead: $+7,987.90 (+3.92%)
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

## Decision Rationale

Accepted as replay-only event allocation lead refinement; no live orders change until a shared adapter and forward outcomes exist.

## Production Impact

Replay only. Production and default backtest order paths are unchanged. A positive live-capital version would need a shared trade-enabled event adapter, run/backtester parity tests, and forward paper replacement-value evidence.
