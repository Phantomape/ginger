# exp-20260521-006 Event Governance-Source Adapter

Decision: `accepted_default_off_event_governance_source_quality_adapter`

Promotes the exp-20260521-005 governance-source quality scout into the shared default-off event adapter.

## Gate 4

| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.6390 | 6.7141 | +0.0751 | $137,454.00 | $138,720.72 | $+1,266.72 |
| mid_weak | 3.6218 | 4.3296 | +0.7078 | $102,311.72 | $111,876.10 | $+9,564.38 |
| old_thin | 0.6850 | 0.7833 | +0.0983 | $43,082.99 | $46,624.77 | $+3,541.78 |

## Adapter Contract

```json
{
  "checks": {
    "broad_governance_source_stacks_to_5x": true,
    "generic_governance_source_2x": true,
    "negative_source_does_not_get_governance_tilt": true,
    "orders_stay_disabled": true,
    "summary_counts_source_quality": true
  },
  "passed": true,
  "snapshot_summary": {
    "candidate_count": 0,
    "deduped_candidate_count": 3,
    "state_surface_addon": {
      "broad_breadth_tilt_candidate_count": 2,
      "broad_breadth_tilt_incremental_notional_usd": 10000.0,
      "candidate_count": 3,
      "eligible_candidate_count": 2,
      "eligible_fraction": 0.6667,
      "eligible_surfaces": [
        "broad_breadth_trend_persistence"
      ],
      "front_rank_rotation_tilt_candidate_count": 0,
      "front_rank_rotation_tilt_incremental_notional_usd": 0,
      "incremental_notional_usd": 65000.0,
      "paper_enabled": true,
      "parameters": {
        "broad_breadth_bucket": "broad_breadth",
        "broad_breadth_tilt_enabled": true,
        "broad_breadth_tilt_scalar": 1.25,
        "eligibility_rule": "score > 0 and state_surface != generic_surface; rotation_breakout_leadership uses rotation_tilt_scalar; front-rank rotation rows use front_rank_rotation_tilt_scalar; broad_breadth rows multiply the active scalar; sec_governance_procedural rows multiply the final paper notional",
        "eligible_scalar": 2.0,
        "front_rank_rotation_max_rank_pct": 0.2,
        "front_rank_rotation_tilt_enabled": true,
        "front_rank_rotation_tilt_scalar": 4.0,
        "generic_surface_not_eligible": "balanced_state_leadership",
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
      "rule_version": "non_generic_positive_state_surface_front_rank_broad_breadth_governance_source_v4",
      "scored_candidate_count": 8,
      "source_quality_tilt_candidate_count": 2,
      "source_quality_tilt_incremental_notional_usd": 35000.0,
      "trade_enabled": false
    },
    "trade_plan_status": "blocked"
  }
}
```

## Production Impact

Shared default-off event adapter/reporting changed. Live/default orders remain disabled.
