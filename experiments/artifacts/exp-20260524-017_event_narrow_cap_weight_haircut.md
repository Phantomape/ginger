# exp-20260524-017 event_narrow_cap_weight_haircut

- lane: `alpha_search`
- decision: `rejected_event_narrow_cap_weight_haircut`
- best_variant: `narrow_cap_weight_025`
- expected_value_score_delta: `0.1646`
- total_pnl_delta: `$2,238.78`
- production_backtest_parity: `none_for_live_orders_replay_only_experiment`

## Hypothesis

In the accepted default-off event overlay, rows tagged narrow_cap_weight_leadership are likely to be crowded cap-weight leadership exposures rather than fresh event alpha. A single paper notional haircut may reduce this weak cohort without changing core entries, exits, ranking, or live orders.

## Gate 4 Before / After

Baseline: `accepted_event_governance_503_adapter`. After: `narrow_cap_weight_025`.

| window | before EV | after EV | delta EV | before PnL | after PnL | delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 8.3761 | 8.4215 | +0.0454 | $170,593.12 | $170,821.47 | $+228.35 |
| mid_weak | 9.6520 | 9.7015 | +0.0495 | $191,507.54 | $191,729.73 | $+222.19 |
| old_thin | 1.6477 | 1.7174 | +0.0697 | $77,719.64 | $79,507.88 | $+1,788.24 |

## Variant Gate Summary

| variant | passed | sample | risk | EV delta | PnL delta | EV windows +/- | max DD drift |
|---|---:|---:|---:|---:|---:|---:|---:|
| narrow_cap_weight_075 | no | yes | yes | +0.0528 | $+746.26 | 3/0 | 0.0000 |
| narrow_cap_weight_050 | no | yes | yes | +0.1001 | $+1,492.52 | 3/0 | 0.0000 |
| narrow_cap_weight_025 | no | yes | yes | +0.1646 | $+2,238.78 | 3/0 | 0.0000 |
| narrow_cap_weight_000 | no | yes | no | -3.9373 | $-37,154.96 | 0/3 | 0.0169 |

## Target Cohort

```json
{
  "target_by_window": {
    "late_strong": {
      "losses": 1,
      "reaction_buckets": [
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_surfaces": [
        "balanced_state_leadership"
      ],
      "tickers": [
        "NFLX"
      ],
      "total_pnl": -304.47,
      "trade_count": 1,
      "wins": 0
    },
    "mid_weak": {
      "losses": 1,
      "reaction_buckets": [
        "negative_excess_0_to_minus_2pct",
        "reaction_-2_to_0"
      ],
      "semantic_subcategories": [
        "",
        "shareholder_vote"
      ],
      "sources": [
        "sec_governance_procedural",
        "sec_negative_reaction"
      ],
      "state_surfaces": [
        "balanced_state_leadership",
        "broad_breadth_trend_persistence"
      ],
      "tickers": [
        "DIS",
        "NOW"
      ],
      "total_pnl": -296.24,
      "trade_count": 2,
      "wins": 1
    },
    "old_thin": {
      "losses": 1,
      "reaction_buckets": [
        "positive_excess_0_to_2pct"
      ],
      "semantic_subcategories": [
        "charter_or_securities_change"
      ],
      "sources": [
        "sec_governance_procedural"
      ],
      "state_surfaces": [
        "broad_breadth_trend_persistence"
      ],
      "tickers": [
        "GS"
      ],
      "total_pnl": -2384.32,
      "trade_count": 1,
      "wins": 0
    }
  },
  "target_field": "event_state_bucket",
  "target_loss_windows_present": 3,
  "target_losses": 3,
  "target_max_single_loss_pnl_share": 0.695399,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "positive_excess_0_to_2pct",
    "reaction_-2_to_0"
  ],
  "target_rule": "state_bucket == narrow_cap_weight_leadership",
  "target_scaled_total_pnl": -2985.03,
  "target_semantic_subcategories": [
    "",
    "charter_or_securities_change",
    "shareholder_vote"
  ],
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_surfaces": [
    "balanced_state_leadership",
    "broad_breadth_trend_persistence"
  ],
  "target_tickers": [
    "DIS",
    "GS",
    "NFLX",
    "NOW"
  ],
  "target_trade_count": 4,
  "target_win_rate": 0.25,
  "target_windows_present": 3,
  "target_wins": 1
}
```

## Production / Backtest Consistency

No production or default-order code changed. This is a default-off replay-only alpha scout.

## Rejection Reason

Best variant `narrow_cap_weight_025` changed aggregate EV by 0.1646 and PnL by 2238.78, but Gate 4 failed: EV improved/regressed windows 3/0, sample_guard_passed=True, risk_guard_passed=True.
