# exp-20260520-044 Event-Rotation Front-Rank Adapter

Decision: `accepted_default_off_event_rotation_front_rank_adapter`

Alpha search. Promotes the exp043 front-rank event-rotation field into shared default-off paper attribution; no live/default orders are enabled.

## Gate 4 Result

| Window | Baseline EV | Adapter EV | Delta EV | Baseline PnL | Adapter PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 6.3077 | 6.6330 | +0.3253 | $132,792.86 | $137,329.40 | $+4,536.54 |
| mid_weak | 3.0800 | 3.3020 | +0.2220 | $93,901.64 | $97,402.83 | $+3,501.19 |
| old_thin | 0.6725 | 0.6725 | +0.0000 | $42,565.76 | $42,565.76 | $+0.00 |

## Adapter Contract

```json
{
  "checks": {
    "front_rank_pct_known": true,
    "front_rank_reason": true,
    "front_rank_scalar_4x": true,
    "non_front_rotation_stays_3x": true,
    "orders_remain_disabled": true,
    "summary_surfaces_field": true
  },
  "front_rank_addon": {
    "adjusted_event_notional_usd": 40000.0,
    "alters_orders": false,
    "base_event_notional_usd": 10000.0,
    "eligible": true,
    "front_rank_rotation_tilt": true,
    "incremental_notional_usd": 30000.0,
    "paper_enabled": true,
    "reason": "eligible_front_rank_rotation_breakout_positive_state_surface",
    "rotation_tilt": true,
    "rule_version": "non_generic_positive_state_surface_front_rank_rotation_tilt_v2",
    "scalar": 4.0,
    "state_decision_date": "2026-05-20",
    "state_rank": 1,
    "state_rank_pct": 0.1,
    "state_score": 1.24,
    "state_surface": "rotation_breakout_leadership",
    "trade_enabled": false
  },
  "non_front_rotation_addon": {
    "adjusted_event_notional_usd": 30000.0,
    "alters_orders": false,
    "base_event_notional_usd": 10000.0,
    "eligible": true,
    "front_rank_rotation_tilt": false,
    "incremental_notional_usd": 20000.0,
    "paper_enabled": true,
    "reason": "eligible_rotation_breakout_positive_state_surface",
    "rotation_tilt": true,
    "rule_version": "non_generic_positive_state_surface_front_rank_rotation_tilt_v2",
    "scalar": 3.0,
    "state_decision_date": "2026-05-20",
    "state_rank": 5,
    "state_rank_pct": 0.5,
    "state_score": 0.71,
    "state_surface": "rotation_breakout_leadership",
    "trade_enabled": false
  },
  "passed": true,
  "summary": {
    "candidate_count": 2,
    "eligible_candidate_count": 2,
    "eligible_fraction": 1.0,
    "eligible_surfaces": [
      "rotation_breakout_leadership"
    ],
    "front_rank_rotation_tilt_candidate_count": 1,
    "front_rank_rotation_tilt_incremental_notional_usd": 30000.0,
    "incremental_notional_usd": 50000.0,
    "paper_enabled": true,
    "parameters": {
      "eligibility_rule": "score > 0 and state_surface != generic_surface; rotation_breakout_leadership uses rotation_tilt_scalar; front-rank rotation rows use front_rank_rotation_tilt_scalar",
      "eligible_scalar": 2.0,
      "front_rank_rotation_max_rank_pct": 0.2,
      "front_rank_rotation_tilt_enabled": true,
      "front_rank_rotation_tilt_scalar": 4.0,
      "generic_surface_not_eligible": "balanced_state_leadership",
      "rotation_tilt_scalar": 3.0,
      "rotation_tilt_surface": "rotation_breakout_leadership"
    },
    "production_impact": {
      "alters_orders": false,
      "alters_sizing": false,
      "scope": "default_off_event_bundle_paper_addon_attribution",
      "trade_enabled": false
    },
    "rotation_tilt_candidate_count": 2,
    "rotation_tilt_incremental_notional_usd": 50000.0,
    "rule_version": "non_generic_positive_state_surface_front_rank_rotation_tilt_v2",
    "scored_candidate_count": 10,
    "trade_enabled": false
  },
  "trade_plan_status": "blocked"
}
```

## Production Impact

Shared default-off adapter/reporting changed. Core entries, ranking, sizing, exits, LLM/news, and live/default orders are unchanged; forward gate remains required before any trade adapter.
