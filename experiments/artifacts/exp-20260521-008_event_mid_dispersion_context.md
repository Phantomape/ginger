# exp-20260521-008 Event Mid-Dispersion Context

Decision: `rejected_event_mid_dispersion_context`

Alpha search, replay-only. Tests whether selected event rows with dispersion_bucket=mid_sector_dispersion deserve extra paper notional on top of the accepted event governance-source adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.7216 | 6.7216 | +0.0000 | $138,876.47 | $138,876.47 | $+0.00 |
| mid_weak | 4.9206 | 5.9023 | +0.9817 | $120,308.77 | $135,685.56 | $+15,376.79 |
| old_thin | 0.8156 | 1.1931 | +0.3775 | $47,976.61 | $61,499.54 | $+13,522.93 |

## Sweep

| Variant | Passed | Sample Guard | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| mid_dispersion_context_125 | no | no | +0.3552 | $+7,224.93 | 2 | 0 | 3 | 2 | 0.5321 |
| mid_dispersion_context_150 | no | no | +0.6981 | $+14,449.86 | 2 | 0 | 3 | 2 | 0.5321 |
| mid_dispersion_context_200 | no | no | +1.3592 | $+28,899.72 | 2 | 0 | 3 | 2 | 0.5321 |

## Selection

```json
{
  "target_breadth_buckets": [
    "broad_breadth",
    "mixed_breadth"
  ],
  "target_by_window": {
    "late_strong": {
      "tickers": [],
      "total_pnl": 0,
      "trade_count": 0,
      "wins": 0
    },
    "mid_weak": {
      "tickers": [
        "CRDO"
      ],
      "total_pnl": 30753.62,
      "trade_count": 1,
      "wins": 1
    },
    "old_thin": {
      "tickers": [
        "CRDO",
        "RTX"
      ],
      "total_pnl": 27045.9,
      "trade_count": 2,
      "wins": 2
    }
  },
  "target_dispersion_bucket": "mid_sector_dispersion",
  "target_max_single_positive_pnl_share": 0.5321,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_scaled_total_pnl": 57799.52,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_surfaces": [
    "broad_breadth_trend_persistence",
    "mid_dispersion_selective_leadership",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "CRDO",
    "RTX"
  ],
  "target_trade_count": 3,
  "target_win_rate": 1.0,
  "target_windows_present": 2,
  "target_wins": 3
}
```

## Production Impact

Replay only. No shared policy, adapter, production report, core behavior, source capacity, or live/default order path changed.

No JavaScript was used.
