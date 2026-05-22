# exp-20260522-005 Event Crowded Leadership Context

Decision: `rejected_event_crowded_leadership_context`

Alpha search. Tests whether generic balanced leadership or narrow cap-weight leadership event rows should receive a paper-notional haircut on top of the accepted event non-narrow context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.2553 | -0.0081 | $169,679.71 | $170,916.57 | $+1,236.86 |
| mid_weak | 9.1661 | 9.3397 | +0.1736 | $187,445.67 | $188,680.40 | $+1,234.73 |
| old_thin | 1.4387 | 1.6925 | +0.2538 | $71,933.84 | $79,086.82 | $+7,152.98 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| crowded_leadership_context_090 | no | yes | yes | +0.0514 | $+1,283.28 | 2 | 1 | 0.0003 |
| crowded_leadership_context_075 | no | yes | yes | +0.1382 | $+3,208.19 | 3 | 0 | 0.0007 |
| crowded_leadership_context_050 | no | yes | yes | +0.2861 | $+6,416.38 | 3 | 0 | 0.0015 |
| crowded_leadership_context_025 | no | yes | yes | +0.4193 | $+9,624.57 | 2 | 1 | 0.0023 |

## Selection

```json
{
  "target_by_window": {
    "late_strong": {
      "losses": 3,
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "balanced_state_leadership"
      ],
      "tickers": [
        "AAPL",
        "DE",
        "INTC",
        "NFLX"
      ],
      "total_pnl": -1649.15,
      "trade_count": 4,
      "wins": 1
    },
    "mid_weak": {
      "losses": 1,
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_buckets": [
        "narrow_cap_weight_leadership",
        "weak_index"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence"
      ],
      "tickers": [
        "DIS",
        "GS",
        "NOW"
      ],
      "total_pnl": -1646.27,
      "trade_count": 3,
      "wins": 2
    },
    "old_thin": {
      "losses": 1,
      "sources": [
        "sec_governance_procedural"
      ],
      "state_buckets": [
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence"
      ],
      "tickers": [
        "GS"
      ],
      "total_pnl": -9537.27,
      "trade_count": 1,
      "wins": 0
    }
  },
  "target_loss_windows_present": 3,
  "target_losses": 5,
  "target_max_single_loss_pnl_share": 0.4589,
  "target_rule": "state_surface == balanced_state_leadership OR state_bucket == narrow_cap_weight_leadership",
  "target_scaled_total_pnl": -12832.69,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "narrow_cap_weight_leadership",
    "weak_index"
  ],
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence"
  ],
  "target_tickers": [
    "AAPL",
    "DE",
    "DIS",
    "GS",
    "INTC",
    "NFLX",
    "NOW"
  ],
  "target_trade_count": 8,
  "target_win_rate": 0.375,
  "target_windows_present": 3,
  "target_wins": 3
}
```

## Production Impact

Shared default-off event adapter/reporting changes only if the experiment is accepted. Core behavior, source capacity, and live/default order paths are unchanged.

No JavaScript was used.
