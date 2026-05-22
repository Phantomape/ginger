# exp-20260522-007 Event Governance 5.03 Haircut

Decision: `accepted_default_off_event_governance_503_haircut`

Alpha search. Tests whether SEC governance/procedural event rows containing 8-K item 5.03 should receive a paper-notional haircut on top of the accepted event non-narrow context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.3761 | +0.1127 | $169,679.71 | $170,593.12 | $+913.41 |
| mid_weak | 9.4589 | 9.6520 | +0.1931 | $190,704.43 | $191,507.54 | $+803.11 |
| old_thin | 1.4387 | 1.6477 | +0.2090 | $71,933.84 | $77,719.64 | $+5,785.80 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| governance_503_075 | no | yes | yes | +0.1705 | $+2,500.78 | 3 | 0 | 0.0000 |
| governance_503_050 | no | yes | yes | +0.3407 | $+5,001.55 | 3 | 0 | 0.0000 |
| governance_503_025 | yes | yes | yes | +0.5148 | $+7,502.32 | 3 | 0 | 0.0000 |
| governance_503_000 | no | yes | no | -3.7132 | $-40,171.90 | 0 | 3 | 0.0163 |

## Selection

```json
{
  "target_by_window": {
    "late_strong": {
      "item_code_sets": [
        "5.03|9.01"
      ],
      "losses": 1,
      "reaction_buckets": [
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change"
      ],
      "state_buckets": [
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "balanced_state_leadership"
      ],
      "tickers": [
        "NFLX"
      ],
      "total_pnl": -1217.88,
      "trade_count": 1,
      "wins": 0
    },
    "mid_weak": {
      "item_code_sets": [
        "5.03|5.07|9.01",
        "5.03|9.01"
      ],
      "losses": 1,
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change",
        "shareholder_vote"
      ],
      "state_buckets": [
        "broad_rotation",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "JPM",
        "NOW"
      ],
      "total_pnl": -1070.82,
      "trade_count": 2,
      "wins": 1
    },
    "old_thin": {
      "item_code_sets": [
        "3.03|5.03|9.01",
        "5.03|9.01"
      ],
      "losses": 1,
      "reaction_buckets": [
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "narrow_cap_weight_leadership"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence"
      ],
      "tickers": [
        "GS"
      ],
      "total_pnl": -7714.34,
      "trade_count": 2,
      "wins": 1
    }
  },
  "target_field": "governance_item_5_03_presence",
  "target_item_code_sets": [
    "3.03|5.03|9.01",
    "5.03|5.07|9.01",
    "5.03|9.01"
  ],
  "target_losses": 3,
  "target_max_single_loss_pnl_share": 0.6954,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct"
  ],
  "target_rule": "source == sec_governance_procedural AND item 5.03 present",
  "target_scaled_total_pnl": -10003.04,
  "target_semantic_subcategories": [
    "charter_or_securities_change",
    "shareholder_vote"
  ],
  "target_sources": [
    "sec_governance_procedural"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation",
    "narrow_cap_weight_leadership"
  ],
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "GS",
    "JPM",
    "NFLX",
    "NOW"
  ],
  "target_trade_count": 5,
  "target_win_rate": 0.4,
  "target_windows_present": 3,
  "target_wins": 2
}
```

## Production Impact

Shared default-off event adapter/reporting changes only because the experiment is accepted. Core behavior, source capacity, and live/default order paths are unchanged.

No JavaScript was used.
