# exp-20260521-010 Event Governance Semantic Cell

Decision: `rejected_event_governance_semantic_cell`

Alpha search, replay-only. Tests whether selected SEC governance/procedural shareholder-vote rows with mild negative first reaction deserve extra paper notional on top of the accepted event adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.6053 | 7.3551 | -0.2502 | $155,210.79 | $152,279.00 | $-2,931.79 |
| mid_weak | 7.6013 | 9.6539 | +2.0526 | $160,365.48 | $203,668.60 | $+43,303.12 |
| old_thin | 1.1813 | 1.8311 | +0.6498 | $61,205.79 | $88,035.14 | $+26,829.35 |

## Sweep

| Variant | Passed | Sample Guard | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| shareholder_vote_negative_110 | no | no | +0.2958 | $+6,720.06 | 2 | 1 | 5 | 3 | 0.3701 |
| shareholder_vote_negative_125 | no | no | +0.7261 | $+16,800.17 | 2 | 1 | 5 | 3 | 0.3701 |
| shareholder_vote_negative_150 | no | no | +1.3768 | $+33,600.33 | 2 | 1 | 5 | 3 | 0.3701 |
| shareholder_vote_negative_200 | no | no | +2.4522 | $+67,200.68 | 2 | 1 | 5 | 3 | 0.3701 |

## Selection

```json
{
  "target_by_window": {
    "late_strong": {
      "tickers": [
        "AAPL"
      ],
      "total_pnl": -5863.6,
      "trade_count": 1,
      "wins": 0
    },
    "mid_weak": {
      "tickers": [
        "GE",
        "NOW",
        "TRIP"
      ],
      "total_pnl": 86606.38,
      "trade_count": 3,
      "wins": 2
    },
    "old_thin": {
      "tickers": [
        "CRDO"
      ],
      "total_pnl": 53658.75,
      "trade_count": 1,
      "wins": 1
    }
  },
  "target_max_single_positive_pnl_share": 0.3701,
  "target_reaction_bucket": "negative_excess_0_to_minus_2pct",
  "target_scaled_total_pnl": 134401.53,
  "target_semantic_subcategory": "shareholder_vote",
  "target_source": "sec_governance_procedural",
  "target_tickers": [
    "AAPL",
    "CRDO",
    "GE",
    "NOW",
    "TRIP"
  ],
  "target_trade_count": 5,
  "target_win_rate": 0.6,
  "target_windows_present": 3,
  "target_wins": 3
}
```

## Production Impact

Replay only. No shared policy, adapter, production report, core behavior, source capacity, or live/default order path changed.

No JavaScript was used.
