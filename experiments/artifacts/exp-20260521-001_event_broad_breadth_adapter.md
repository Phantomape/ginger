# exp-20260521-001 Event Broad-Breadth Adapter

Decision: `accepted_default_off_event_broad_breadth_adapter`

Alpha search. Tests broad-breadth event quality on top of the accepted default-off event front-rank adapter; no live/default orders are enabled.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.6330 | 6.6390 | +0.0060 | $137,329.40 | $137,454.00 | $+124.60 |
| mid_weak | 3.3020 | 3.6218 | +0.3198 | $97,402.83 | $102,311.72 | $+4,908.89 |
| old_thin | 0.6725 | 0.6850 | +0.0125 | $42,565.76 | $43,082.99 | $+517.23 |

## Sweep

| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| broad_breadth_110 | no | +0.1318 | $+2,220.29 | 3 | 0 | 15 | 3 | 0.3882 |
| broad_breadth_120 | yes | +0.2704 | $+4,440.59 | 3 | 0 | 15 | 3 | 0.3882 |
| broad_breadth_125 | yes | +0.3383 | $+5,550.72 | 3 | 0 | 15 | 3 | 0.3882 |

## Selection

```json
{
  "target_breadth_bucket": "broad_breadth",
  "target_by_window": {
    "late_strong": {
      "tickers": [
        "ISRG",
        "MCD"
      ],
      "total_pnl": 623.0,
      "trade_count": 2,
      "wins": 2
    },
    "mid_weak": {
      "tickers": [
        "CRDO",
        "GE",
        "GS",
        "JPM",
        "MCD",
        "NOW",
        "TRIP"
      ],
      "total_pnl": 24544.44,
      "trade_count": 8,
      "wins": 7
    },
    "old_thin": {
      "tickers": [
        "CRDO",
        "GS",
        "MCD"
      ],
      "total_pnl": 2586.19,
      "trade_count": 5,
      "wins": 3
    }
  },
  "target_max_single_positive_pnl_share": 0.3882,
  "target_scaled_total_pnl": 27753.63,
  "target_tickers": [
    "CRDO",
    "GE",
    "GS",
    "ISRG",
    "JPM",
    "MCD",
    "NOW",
    "TRIP"
  ],
  "target_trade_count": 15,
  "target_win_rate": 0.8,
  "target_windows_present": 3,
  "target_wins": 12
}
```

## Production Impact

Shared default-off adapter/reporting changed. Core entries, ranking, sizing, exits, LLM/news, and live/default orders are unchanged; forward gate remains required before any trade adapter.
