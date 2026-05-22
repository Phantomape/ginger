# exp-20260522-006 Event Governance No-5.03 Disclosure Quality

Decision: `rejected_event_governance_no_503_disclosure_quality`

Alpha search. Tests whether SEC governance/procedural event rows without item 5.03 should receive a paper-notional boost on top of the accepted event non-narrow context adapter.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.2634 | 7.8095 | -0.4539 | $169,679.71 | $170,512.21 | $+832.50 |
| mid_weak | 9.4589 | 12.0757 | +2.6168 | $190,704.43 | $251,577.24 | $+60,872.81 |
| old_thin | 1.4387 | 2.3528 | +0.9141 | $71,933.84 | $112,572.76 | $+40,638.92 |

## Sweep

| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |
|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|
| governance_no_503_110 | no | yes | no | +0.3909 | $+10,234.43 | 2 | 1 | 0.0143 |
| governance_no_503_125 | no | yes | no | +0.9690 | $+25,586.05 | 2 | 1 | 0.0351 |
| governance_no_503_150 | no | yes | no | +1.7669 | $+51,172.12 | 2 | 1 | 0.0681 |
| governance_no_503_200 | no | yes | no | +3.0770 | $+102,344.23 | 2 | 1 | 0.1284 |

## Selection

```json
{
  "target_by_window": {
    "late_strong": {
      "item_code_sets": [
        "3.02",
        "5.07|9.01",
        "9.01"
      ],
      "losses": 2,
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change",
        "exhibit_only",
        "shareholder_vote"
      ],
      "state_buckets": [
        "balanced_risk_on",
        "broad_rotation"
      ],
      "tickers": [
        "AAPL",
        "GS",
        "INTC"
      ],
      "total_pnl": 832.52,
      "trade_count": 3,
      "wins": 1
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
      "tickers": [
        "CRDO",
        "GS"
      ],
      "total_pnl": 40638.95,
      "trade_count": 2,
      "wins": 2
    }
  },
  "target_field": "governance_no_5_03_disclosure_quality",
  "target_item_code_sets": [
    "3.02",
    "5.07",
    "5.07|9.01",
    "9.01"
  ],
  "target_losses": 2,
  "target_max_single_positive_pnl_share": 0.3566,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct"
  ],
  "target_rule": "source == sec_governance_procedural AND item 5.03 absent",
  "target_scaled_total_pnl": 102344.33,
  "target_semantic_subcategories": [
    "charter_or_securities_change",
    "exhibit_only",
    "shareholder_vote"
  ],
  "target_sources": [
    "sec_governance_procedural"
  ],
  "target_tickers": [
    "AAPL",
    "CRDO",
    "GE",
    "GS",
    "INTC",
    "TRIP"
  ],
  "target_trade_count": 8,
  "target_win_rate": 0.75,
  "target_windows_present": 3,
  "target_wins": 6
}
```

## Production Impact

Shared default-off event adapter/reporting changes only if the experiment is accepted. Core behavior, source capacity, and live/default order paths are unchanged.

No JavaScript was used.
