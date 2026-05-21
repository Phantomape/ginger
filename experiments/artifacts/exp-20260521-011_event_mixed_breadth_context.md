# exp-20260521-011 Event Mixed-Breadth Context

Decision: `rejected_event_mixed_breadth_context`

Alpha search, replay-only. Tests whether selected mixed-breadth event rows deserve a different paper-notional scalar on top of the accepted event adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.6053 | 8.0586 | +0.4533 | $155,210.79 | $164,126.49 | $+8,915.70 |
| mid_weak | 7.6013 | 7.5665 | -0.0348 | $160,365.48 | $159,969.17 | $-396.31 |
| old_thin | 1.1813 | 1.1954 | +0.0141 | $61,205.79 | $61,620.22 | $+414.43 |

## Sweep

| Variant | Passed | Sample Guard | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| mixed_breadth_context_050 | no | no | -1.0381 | $-17,867.66 | 1 | 2 | 11 | 3 | 0.7931 |
| mixed_breadth_context_075 | no | no | -0.4892 | $-8,933.83 | 1 | 2 | 11 | 3 | 0.7931 |
| mixed_breadth_context_090 | no | no | -0.2068 | $-3,573.54 | 1 | 2 | 11 | 3 | 0.7931 |
| mixed_breadth_context_110 | no | no | +0.1864 | $+3,573.53 | 2 | 1 | 11 | 3 | 0.7931 |
| mixed_breadth_context_125 | no | no | +0.4326 | $+8,933.82 | 2 | 1 | 11 | 3 | 0.7931 |

## Selection

```json
{
  "target_breadth_bucket": "mixed_breadth",
  "target_by_window": {
    "late_strong": {
      "dispersion_buckets": [
        "",
        "high_sector_dispersion"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_surfaces": [
        "",
        "balanced_state_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "AAPL",
        "DE",
        "GS",
        "INTC",
        "LITE",
        "NFLX"
      ],
      "total_pnl": 44578.58,
      "trade_count": 7,
      "wins": 3
    },
    "mid_weak": {
      "dispersion_buckets": [
        "high_sector_dispersion"
      ],
      "sources": [
        "sec_negative_reaction"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "DIS",
        "GS"
      ],
      "total_pnl": 1498.85,
      "trade_count": 2,
      "wins": 2
    },
    "old_thin": {
      "dispersion_buckets": [
        "high_sector_dispersion",
        "mid_sector_dispersion"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_surfaces": [
        "mid_dispersion_selective_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "GS",
        "RTX"
      ],
      "total_pnl": 2072.15,
      "trade_count": 2,
      "wins": 2
    }
  },
  "target_dispersion_buckets": [
    "",
    "high_sector_dispersion",
    "mid_sector_dispersion"
  ],
  "target_max_single_positive_pnl_share": 0.7931,
  "target_scaled_total_pnl": 48149.58,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_surfaces": [
    "",
    "balanced_state_leadership",
    "mid_dispersion_selective_leadership",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "AAPL",
    "DE",
    "DIS",
    "GS",
    "INTC",
    "LITE",
    "NFLX",
    "RTX"
  ],
  "target_trade_count": 11,
  "target_win_rate": 0.6364,
  "target_windows_present": 3,
  "target_wins": 7
}
```

## Production Impact

Replay only. No shared policy, adapter, production report, core behavior, source capacity, or live/default order path changed.

No JavaScript was used.
