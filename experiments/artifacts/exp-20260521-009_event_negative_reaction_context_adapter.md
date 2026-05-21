# exp-20260521-009 Event Negative-Reaction Context Adapter

Decision: `accepted_default_off_event_negative_reaction_context_adapter`

Alpha search. Tests and promotes a shared default-off paper notional scalar for selected event rows in negative first-reaction buckets.

## Gate 4 Result

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.7216 | 7.6053 | +0.8837 | $138,876.47 | $155,210.79 | $+16,334.32 |
| mid_weak | 4.9206 | 7.6013 | +2.6807 | $120,308.77 | $160,365.48 | $+40,056.71 |
| old_thin | 0.8156 | 1.1813 | +0.3657 | $47,976.61 | $61,205.79 | $+13,229.18 |

## Sweep

| Variant | Passed | Sample Guard | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |
|---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| negative_reaction_context_125 | yes | yes | +1.0290 | $+17,405.06 | 3 | 0 | 20 | 3 | 0.2397 |
| negative_reaction_context_150 | yes | yes | +2.0327 | $+34,810.10 | 3 | 0 | 20 | 3 | 0.2397 |
| negative_reaction_context_200 | yes | yes | +3.9301 | $+69,620.21 | 3 | 0 | 20 | 3 | 0.2397 |

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
        "AAPL",
        "DE",
        "GS",
        "ISRG",
        "LITE",
        "MCD"
      ],
      "total_pnl": 32668.66,
      "trade_count": 7,
      "wins": 4
    },
    "mid_weak": {
      "tickers": [
        "CRDO",
        "DIS",
        "GE",
        "GS",
        "MCD",
        "NOW",
        "TRIP"
      ],
      "total_pnl": 82897.77,
      "trade_count": 9,
      "wins": 8
    },
    "old_thin": {
      "tickers": [
        "CRDO",
        "GS",
        "MCD",
        "RTX"
      ],
      "total_pnl": 26458.37,
      "trade_count": 4,
      "wins": 3
    }
  },
  "target_dispersion_buckets": [
    "",
    "high_sector_dispersion",
    "mid_sector_dispersion"
  ],
  "target_max_single_positive_pnl_share": 0.2397,
  "target_reaction_buckets": [
    "negative_excess_0_to_minus_2pct",
    "reaction_-2_to_0",
    "reaction_-5_to_-2"
  ],
  "target_scaled_total_pnl": 142024.8,
  "target_sources": [
    "sec_governance_procedural",
    "sec_negative_reaction"
  ],
  "target_state_surfaces": [
    "",
    "balanced_state_leadership",
    "broad_breadth_trend_persistence",
    "mid_dispersion_selective_leadership",
    "rotation_breakout_leadership"
  ],
  "target_tickers": [
    "AAPL",
    "CRDO",
    "DE",
    "DIS",
    "GE",
    "GS",
    "ISRG",
    "LITE",
    "MCD",
    "NOW",
    "RTX",
    "TRIP"
  ],
  "target_trade_count": 20,
  "target_win_rate": 0.75,
  "target_windows_present": 3,
  "target_wins": 15
}
```

## Adapter Contract

```json
{
  "checks": {
    "governance_generic_negative_reaction_stacks_to_4x": true,
    "negative_source_broad_reaction_stacks_to_5x": true,
    "orders_stay_disabled": true,
    "positive_reaction_does_not_get_reaction_tilt": true,
    "summary_counts_negative_reaction": true
  },
  "passed": true,
  "snapshot_summary": {
    "candidate_count": 0,
    "deduped_candidate_count": 3,
    "state_surface_addon": {
      "broad_breadth_tilt_candidate_count": 1,
      "broad_breadth_tilt_incremental_notional_usd": 5000.0,
      "candidate_count": 3,
      "eligible_candidate_count": 1,
      "eligible_fraction": 0.3333,
      "eligible_surfaces": [
        "broad_breadth_trend_persistence"
      ],
      "front_rank_rotation_tilt_candidate_count": 0,
      "front_rank_rotation_tilt_incremental_notional_usd": 0,
      "incremental_notional_usd": 80000.0,
      "negative_reaction_tilt_candidate_count": 2,
      "negative_reaction_tilt_incremental_notional_usd": 45000.0,
      "paper_enabled": true,
      "parameters": {
        "broad_breadth_bucket": "broad_breadth",
        "broad_breadth_tilt_enabled": true,
        "broad_breadth_tilt_scalar": 1.25,
        "eligibility_rule": "score > 0 and state_surface != generic_surface; rotation_breakout_leadership uses rotation_tilt_scalar; front-rank rotation rows use front_rank_rotation_tilt_scalar; broad_breadth rows multiply the active scalar; sec_governance_procedural rows multiply the current paper notional; negative reaction buckets multiply the final paper notional",
        "eligible_scalar": 2.0,
        "front_rank_rotation_max_rank_pct": 0.2,
        "front_rank_rotation_tilt_enabled": true,
        "front_rank_rotation_tilt_scalar": 4.0,
        "generic_surface_not_eligible": "balanced_state_leadership",
        "negative_reaction_buckets": [
          "negative_excess_0_to_minus_2pct",
          "reaction_-2_to_0",
          "reaction_-5_to_-2"
        ],
        "negative_reaction_tilt_enabled": true,
        "negative_reaction_tilt_scalar": 2.0,
        "rotation_tilt_scalar": 3.0,
        "rotation_tilt_surface": "rotation_breakout_leadership",
        "source_quality_source": "sec_governance_procedural",
        "source_quality_tilt_enabled": true,
        "source_quality_tilt_scalar": 2.0
      },
      "production_impact": {
        "alters_orders": false,
        "alters_sizing": false,
        "scope": "default_off_event_bundle_paper_addon_attribution",
        "trade_enabled": false
      },
      "rotation_tilt_candidate_count": 0,
      "rotation_tilt_incremental_notional_usd": 0,
      "rule_version": "non_generic_positive_state_surface_front_rank_broad_breadth_governance_source_negative_reaction_v5",
      "scored_candidate_count": 8,
      "source_quality_tilt_candidate_count": 2,
      "source_quality_tilt_incremental_notional_usd": 20000.0,
      "trade_enabled": false
    },
    "trade_plan_status": "blocked"
  }
}
```

## Production Impact

Shared default-off event adapter/reporting changed. Live/default orders remain disabled.

No JavaScript was used.
