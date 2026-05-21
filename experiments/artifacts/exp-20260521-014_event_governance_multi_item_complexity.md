# exp-20260521-014 Event Governance Multi-Item Complexity

Decision: `rejected_event_governance_multi_item_complexity`

Alpha search. Tests whether SEC governance/procedural rows with multiple 8-K item codes deserve a paper-notional scalar on top of the accepted event non-narrow state context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 8.6356 | +0.3722 | $169,679.71 | $173,753.95 | $+4,074.24 |
| mid_weak | 9.4589 | 9.6520 | +0.1931 | $190,704.43 | $191,507.54 | $+803.11 |
| old_thin | 1.4387 | 1.6477 | +0.2090 | $71,933.84 | $77,719.64 | $+5,785.80 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| multi_item_complexity_000 | no | no | yes | -4.1800 | $-45,992.46 | 0 | 3 | 0.0163 |
| multi_item_complexity_025 | no | no | yes | +0.7743 | $+10,663.15 | 3 | 0 | 0.0000 |
| multi_item_complexity_050 | no | no | yes | +0.5130 | $+7,108.77 | 3 | 0 | 0.0000 |
| multi_item_complexity_075 | no | no | yes | +0.2562 | $+3,554.39 | 3 | 0 | 0.0000 |
| multi_item_complexity_125 | no | no | yes | -0.2775 | $-3,554.39 | 0 | 3 | 0.0003 |

## Selection

```json
{
  "min_item_code_count": 2,
  "target_by_window": {
    "late_strong": {
      "item_code_sets": [
        "5.03|9.01",
        "5.07|9.01"
      ],
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change",
        "shareholder_vote"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "narrow_cap_weight_leadership"
      ],
      "tickers": [
        "AAPL",
        "NFLX"
      ],
      "total_pnl": -1358.09,
      "trade_count": 2,
      "wins": 0
    },
    "mid_weak": {
      "item_code_sets": [
        "5.03|5.07|9.01",
        "5.03|9.01"
      ],
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change",
        "shareholder_vote"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_buckets": [
        "broad_rotation",
        "narrow_cap_weight_leadership"
      ],
      "tickers": [
        "JPM",
        "NOW"
      ],
      "total_pnl": -267.7,
      "trade_count": 2,
      "wins": 1
    },
    "old_thin": {
      "item_code_sets": [
        "3.03|5.03|9.01",
        "5.03|9.01"
      ],
      "reaction_buckets": [
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "narrow_cap_weight_leadership"
      ],
      "tickers": [
        "GS"
      ],
      "total_pnl": -1928.59,
      "trade_count": 2,
      "wins": 1
    }
  },
  "target_field": "eight_k_item_code_count",
  "target_item_code_sets": [
    "3.03|5.03|9.01",
    "5.03|5.07|9.01",
    "5.03|9.01",
    "5.07|9.01"
  ],
  "target_max_single_positive_pnl_share": 0.5089,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct"
  ],
  "target_scaled_total_pnl": -3554.38,
  "target_semantic_subcategories": [
    "charter_or_securities_change",
    "shareholder_vote"
  ],
  "target_source": "sec_governance_procedural",
  "target_sources": [
    "sec_governance_procedural"
  ],
  "target_state_buckets": [
    "balanced_risk_on",
    "broad_rotation",
    "narrow_cap_weight_leadership"
  ],
  "target_tickers": [
    "AAPL",
    "GS",
    "JPM",
    "NFLX",
    "NOW"
  ],
  "target_trade_count": 6,
  "target_win_rate": 0.3333,
  "target_windows_present": 3,
  "target_wins": 2
}
```

## Production Impact

No shared policy, production adapter, run adapter, order path, source capacity, or core behavior changed.

No JavaScript was used.
