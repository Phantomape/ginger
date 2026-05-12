# exp-20260512-100 Space Event-State Replacement Manifest

Generated at: 2026-05-12T18:30:17+00:00

## Scope
Read-only measurement repair. This artifact inventories the existing Space catalyst event-state shadow ledger and does not change entries, exits, filters, ranking, sizing, risk budgets, prompts, orders, or production adapters.

## Alpha Blocker
Concrete alpha hypothesis: Space official-catalyst promotion/risk allocation should be tested only on catalyst families with closed forward replacement-value evidence. The blocker was not knowing which existing forward rows had mature direct, benchmark, same-theme, or core replacement fields.

## Coverage Summary
- ledger_rows: `18`
- closed_decisions: `12`
- pending_decisions: `6`
- closed_decision_rate: `0.666667`
- closed_horizon_rows: `48`
- cash_relative_coverage_rate: `0.770833`
- same_theme_replacement_coverage_rate: `0.770833`
- spy_relative_coverage_rate: `0.770833`
- qqq_relative_coverage_rate: `0.770833`
- core_replacement_coverage_rate: `0.0`
- closed_horizons_with_pending_core_replacement_status: `37`

## Decision
Observed-only. Cash-relative, SPY-relative, QQQ-relative, and same-theme forward attribution are mature for 37 of 48 closed horizon rows; core replacement value remains unavailable because all mature closed horizon rows still carry pending core-replacement status.

## Manifest JSON
```json
{
  "alpha_unblocked": "Space catalyst family/source/profile forward tests can now use closed cash, SPY, QQQ, UFO/ARKX in source summary, and same-theme replacement-value slices; core-slot replacement promotion remains blocked until core_replacement_value closes.",
  "by_semantic_bucket_coverage": {
    "attention_only": {
      "cash_value_horizons": 0,
      "closed": 0,
      "core_value_horizons": 0,
      "horizon_rows": 0,
      "pending": 5,
      "qqq_value_horizons": 0,
      "spy_value_horizons": 0,
      "theme_value_horizons": 0
    },
    "defense_budget_theme": {
      "cash_value_horizons": 30,
      "closed": 10,
      "core_value_horizons": 0,
      "horizon_rows": 40,
      "pending": 0,
      "qqq_value_horizons": 30,
      "spy_value_horizons": 30,
      "theme_value_horizons": 30
    },
    "fundamental_contract_regulatory": {
      "cash_value_horizons": 7,
      "closed": 2,
      "core_value_horizons": 0,
      "horizon_rows": 8,
      "pending": 1,
      "qqq_value_horizons": 7,
      "spy_value_horizons": 7,
      "theme_value_horizons": 7
    }
  },
  "cash_relative_coverage_rate": 0.770833,
  "closed_by_event_field": {
    "customer_win": 2,
    "government_space_contract": 11
  },
  "closed_by_semantic_bucket": {
    "defense_budget_theme": 10,
    "fundamental_contract_regulatory": 2
  },
  "closed_by_source_type": {
    "official_government_release": 10,
    "official_or_primary_release": 1,
    "official_regulatory_release": 1
  },
  "closed_by_theme_segment": {
    "launch_lunar": 3,
    "satellite_connectivity": 6,
    "space_data_defense": 3
  },
  "closed_decision_rate": 0.666667,
  "closed_decisions": 12,
  "closed_horizon_rows": 48,
  "closed_horizons_with_cash_relative_pnl": 37,
  "closed_horizons_with_core_replacement_value": 0,
  "closed_horizons_with_pending_core_replacement_status": 37,
  "closed_horizons_with_qqq_relative_value": 37,
  "closed_horizons_with_same_theme_replacement_value": 37,
  "closed_horizons_with_spy_relative_value": 37,
  "core_replacement_coverage_rate": 0.0,
  "decision": "observed_only_core_replacement_still_blocked",
  "ledger_path": "data/space_catalyst_event_state_shadow_ledger.jsonl",
  "ledger_rows": 18,
  "pending_decisions": 6,
  "production_impact": {
    "alters_candidate_ranking": false,
    "alters_orders": false,
    "alters_signal_generation": false,
    "alters_sizing": false,
    "backtester_adapter_changed": false,
    "parity_test_added": false,
    "replay_only": false,
    "run_adapter_changed": false,
    "shared_policy_changed": false
  },
  "qqq_relative_coverage_rate": 0.770833,
  "same_theme_replacement_coverage_rate": 0.770833,
  "spy_relative_coverage_rate": 0.770833,
  "strategy_behavior_changed": false,
  "summary_path": "data/space_catalyst_event_state_shadow_summary.json",
  "summary_promotion_gate": {
    "checks": {
      "minimum_closed_decisions": true,
      "official_bucket_has_closed_decision": true,
      "positive_10d_arkx_relative_value": true,
      "positive_10d_return": true,
      "positive_10d_same_theme_value": false,
      "positive_10d_ufo_relative_value": true
    },
    "closed_decision_count": 12,
    "minimum_closed_decisions": 10,
    "mode": "observe_only",
    "official_closed_decision_count": 12,
    "passed": false,
    "reason": "insufficient_closed_official_forward_replacement_value"
  }
}
```
