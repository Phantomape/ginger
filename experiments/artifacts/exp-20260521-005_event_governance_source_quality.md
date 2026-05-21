# exp-20260521-005 Event Governance-Source Quality

Decision: `promising_replay_only_event_governance_source_quality`

Alpha search, replay-only. Tests whether selected sec_governance_procedural event rows deserve extra paper notional on top of the accepted default-off event broad-breadth adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.6390 | 6.7141 | +0.0751 | $137,454.00 | $138,720.72 | $+1,266.72 |
| mid_weak | 3.6218 | 4.3296 | +0.7078 | $102,311.72 | $111,876.10 | $+9,564.38 |
| old_thin | 0.6850 | 0.7833 | +0.0983 | $43,082.99 | $46,624.77 | $+3,541.78 |

## Sweep

| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| governance_source_125 | no | +0.2110 | $+3,593.23 | 3 | 0 | 13 | 3 | 0.2749 |
| governance_source_150 | yes | +0.4464 | $+7,186.44 | 3 | 0 | 13 | 3 | 0.2749 |
| governance_source_175 | yes | +0.6618 | $+10,779.67 | 3 | 0 | 13 | 3 | 0.2749 |
| governance_source_200 | yes | +0.8812 | $+14,372.88 | 3 | 0 | 13 | 3 | 0.2749 |

## Selection

```json
{
  "target_breadth_buckets": [
    "broad_breadth",
    "mixed_breadth",
    "thin_breadth"
  ],
  "target_by_window": {
    "late_strong": {
      "tickers": [
        "AAPL",
        "GS",
        "INTC",
        "NFLX"
      ],
      "total_pnl": 2533.44,
      "trade_count": 4,
      "wins": 1
    },
    "mid_weak": {
      "tickers": [
        "GE",
        "GS",
        "JPM",
        "NOW",
        "TRIP"
      ],
      "total_pnl": 19128.77,
      "trade_count": 5,
      "wins": 4
    },
    "old_thin": {
      "tickers": [
        "CRDO",
        "GS"
      ],
      "total_pnl": 7083.6,
      "trade_count": 4,
      "wins": 3
    }
  },
  "target_max_single_positive_pnl_share": 0.2749,
  "target_scaled_total_pnl": 28745.81,
  "target_source": "sec_governance_procedural",
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "AAPL",
    "CRDO",
    "GE",
    "GS",
    "INTC",
    "JPM",
    "NFLX",
    "NOW",
    "TRIP"
  ],
  "target_trade_count": 13,
  "target_win_rate": 0.6154,
  "target_windows_present": 3,
  "target_wins": 8
}
```

## Production Impact

Replay only. No shared policy, adapter, production report, core behavior, source capacity, or live/default order path changed.
