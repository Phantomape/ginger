# exp-20260523-008 Event Governance Clean No-5.03 After 5.03 Haircut

Decision: `rejected_event_governance_clean_no503_after503`

Alpha search, replay-only. Tests whether SEC governance/procedural event rows without item 5.03 and with semantic_subcategory in exhibit_only/shareholder_vote deserve a paper-notional boost on top of the accepted 5.03 governance haircut.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.3761 | 7.3002 | -1.0759 | $170,593.12 | $164,790.61 | $-5,802.51 |
| mid_weak | 9.6520 | 12.2152 | +2.5632 | $191,507.54 | $252,380.35 | $+60,872.81 |
| old_thin | 1.6477 | 2.5565 | +0.9088 | $77,719.64 | $118,358.56 | $+40,638.92 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| clean_no503_1025 | no | yes | yes | +0.0820 | $+2,392.73 | 2 | 1 | 0.0036 |
| clean_no503_105 | no | yes | yes | +0.1755 | $+4,785.45 | 2 | 1 | 0.0072 |
| clean_no503_110 | no | yes | no | +0.3325 | $+9,570.92 | 2 | 1 | 0.0143 |
| clean_no503_125 | no | yes | no | +0.7808 | $+23,927.29 | 2 | 1 | 0.0351 |
| clean_no503_150 | no | yes | no | +1.3968 | $+47,854.61 | 2 | 1 | 0.0681 |
| clean_no503_200 | no | yes | no | +2.3961 | $+95,709.22 | 2 | 1 | 0.1284 |

## Selection

```json
{
  "target_by_window": {
    "late_strong": {
      "item_code_sets": [
        "5.07|9.01",
        "9.01"
      ],
      "losses": 2,
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct"
      ],
      "semantic_subcategories": [
        "exhibit_only",
        "shareholder_vote"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "AAPL",
        "GS"
      ],
      "total_pnl": -5802.5,
      "trade_count": 2,
      "wins": 0
    },
    "mid_weak": {
      "item_code_sets": [
        "5.07",
        "9.01"
      ],
      "losses": 0,
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "exhibit_only",
        "shareholder_vote"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation",
        "weak_index"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "GE",
        "GS",
        "TRIP"
      ],
      "total_pnl": 60872.86,
      "trade_count": 3,
      "wins": 3
    },
    "old_thin": {
      "item_code_sets": [
        "5.07",
        "9.01"
      ],
      "losses": 0,
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "exhibit_only",
        "shareholder_vote"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence",
        "rotation_breakout_leadership"
      ],
      "tickers": [
        "CRDO",
        "GS"
      ],
      "total_pnl": 40638.95,
      "trade_count": 2,
      "wins": 2
    }
  },
  "target_field": "governance_clean_no_5_03_semantic_subcategory",
  "target_item_code_sets": [
    "5.07",
    "5.07|9.01",
    "9.01"
  ],
  "target_losses": 2,
  "target_max_single_positive_pnl_share": 0.3799,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct"
  ],
  "target_rule": "source == sec_governance_procedural AND item 5.03 absent AND semantic_subcategory in ['exhibit_only', 'shareholder_vote']",
  "target_scaled_total_pnl": 95709.31,
  "target_semantic_subcategories": [
    "exhibit_only",
    "shareholder_vote"
  ],
  "target_sources": [
    "sec_governance_procedural"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation",
    "weak_index"
  ],
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
    "TRIP"
  ],
  "target_trade_count": 7,
  "target_win_rate": 0.7143,
  "target_windows_present": 3,
  "target_wins": 5
}
```

## Production Impact

Replay-only. No shared default-off adapter, run adapter, core strategy behavior, or live/default order path changed. If a future variant passes, it still needs shared-policy promotion before it can be treated as accepted.

No JavaScript was used.
