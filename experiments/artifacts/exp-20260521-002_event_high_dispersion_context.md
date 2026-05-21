# exp-20260521-002 Event High-Dispersion Context

Decision: `rejected_event_high_dispersion_context`

Alpha search, replay-only. Tests whether high sector dispersion is a useful event-context allocation field on top of the accepted default-off event broad-breadth adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.6390 | 6.9543 | +0.3153 | $137,454.00 | $142,214.99 | $+4,760.99 |
| mid_weak | 3.6218 | 3.8318 | +0.2100 | $102,311.72 | $105,268.86 | $+2,957.14 |
| old_thin | 0.6850 | 0.6726 | -0.0124 | $43,082.99 | $42,568.22 | $-514.77 |

## Sweep

| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| high_dispersion_105 | no | +0.0999 | $+1,440.68 | 2 | 1 | 23 | 3 | 0.4938 |
| high_dispersion_110 | no | +0.1999 | $+2,881.35 | 2 | 1 | 23 | 3 | 0.4938 |
| high_dispersion_115 | no | +0.3102 | $+4,322.02 | 2 | 1 | 23 | 3 | 0.4938 |
| high_dispersion_125 | no | +0.5129 | $+7,203.36 | 2 | 1 | 23 | 3 | 0.4938 |

## Selection

```json
{
  "target_by_window": {
    "late_strong": {
      "tickers": [
        "AAPL",
        "DE",
        "GS",
        "INTC",
        "ISRG",
        "LITE",
        "MCD",
        "NFLX"
      ],
      "total_pnl": 23804.96,
      "trade_count": 8,
      "wins": 4
    },
    "mid_weak": {
      "tickers": [
        "CRDO",
        "DIS",
        "GE",
        "GS",
        "JPM",
        "MCD",
        "NOW",
        "TRIP"
      ],
      "total_pnl": 16525.85,
      "trade_count": 10,
      "wins": 9
    },
    "old_thin": {
      "tickers": [
        "GS",
        "MCD"
      ],
      "total_pnl": -2573.87,
      "trade_count": 5,
      "wins": 3
    }
  },
  "target_dispersion_bucket": "high_sector_dispersion",
  "target_max_single_positive_pnl_share": 0.4938,
  "target_scaled_total_pnl": 37756.94,
  "target_tickers": [
    "AAPL",
    "CRDO",
    "DE",
    "DIS",
    "GE",
    "GS",
    "INTC",
    "ISRG",
    "JPM",
    "LITE",
    "MCD",
    "NFLX",
    "NOW",
    "TRIP"
  ],
  "target_trade_count": 23,
  "target_win_rate": 0.6957,
  "target_windows_present": 3,
  "target_wins": 16
}
```

## Production Impact

Replay only. No shared policy, adapter, production report, core behavior, or live/default order path changed.
