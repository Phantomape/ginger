# exp-20260521-007 Event Negative Phrase Evidence

Decision: `rejected_event_negative_phrase_evidence`

Alpha search, replay-only. Tests whether selected SEC negative-reaction event rows with negative_phrase_hits >= 3 deserve extra paper notional on top of the accepted event governance-source adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.7216 | 7.9080 | +1.1864 | $138,876.47 | $156,594.34 | $+17,717.87 |
| mid_weak | 4.9206 | 6.0895 | +1.1689 | $120,308.77 | $138,713.92 | $+18,405.15 |
| old_thin | 0.8156 | 0.8077 | -0.0079 | $47,976.61 | $47,791.11 | $-185.50 |

## Sweep

| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| negative_phrase_evidence_125 | no | +0.6145 | $+8,984.39 | 2 | 1 | 13 | 3 | 0.4673 |
| negative_phrase_evidence_150 | no | +1.2158 | $+17,968.75 | 2 | 1 | 13 | 3 | 0.4673 |
| negative_phrase_evidence_175 | no | +1.7860 | $+26,953.14 | 2 | 1 | 13 | 3 | 0.4673 |
| negative_phrase_evidence_200 | no | +2.3474 | $+35,937.52 | 2 | 1 | 13 | 3 | 0.4673 |

## Selection

```json
{
  "target_breadth_buckets": [
    "broad_breadth",
    "mixed_breadth"
  ],
  "target_by_window": {
    "late_strong": {
      "tickers": [
        "DE",
        "LITE",
        "MCD"
      ],
      "total_pnl": 35435.77,
      "trade_count": 4,
      "wins": 3
    },
    "mid_weak": {
      "tickers": [
        "CRDO",
        "DIS",
        "GS",
        "MCD"
      ],
      "total_pnl": 39594.58,
      "trade_count": 6,
      "wins": 6
    },
    "old_thin": {
      "tickers": [
        "GS",
        "MCD",
        "RTX"
      ],
      "total_pnl": -371.01,
      "trade_count": 3,
      "wins": 2
    }
  },
  "target_max_single_positive_pnl_share": 0.4673,
  "target_negative_phrase_hits_min": 3,
  "target_reaction_buckets": [
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_scaled_total_pnl": 74659.34,
  "target_source": "sec_negative_reaction",
  "target_state_surfaces": [
    "",
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "mid_dispersion_selective_leadership",
    "rotation_breakout_leadership"
  ],
  "target_text_event_types": [
    "earnings_release_text",
    "item_2_02_other_text"
  ],
  "target_tickers": [
    "CRDO",
    "DE",
    "DIS",
    "GS",
    "LITE",
    "MCD",
    "RTX"
  ],
  "target_trade_count": 13,
  "target_win_rate": 0.8462,
  "target_windows_present": 3,
  "target_wins": 11
}
```

## Production Impact

Replay only. No shared policy, adapter, production report, core behavior, source capacity, or live/default order path changed.
