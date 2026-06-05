# exp-20260605-012 Space Same-Theme Activation Readiness

Decision: `rejected_space_same_theme_activation_readiness`.

This is a read-only activation-readiness audit. It does not enable Space production slots.

## Preflight

- Hypothesis: Official Space catalyst forward rows may contain a production-visible sub-cohort that passes 10d same-theme replacement value even though the aggregate Space shadow universe does not.
- Single causal variable: `space_official_cohort_10d_same_theme_replacement_activation_scope_v1`
- Prior experiments: `exp-20260528-026, exp-20260529-020, exp-20260531-022, exp-20260602-025, exp-20260513-113, exp-20260514-009`
- Repro command: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_012_space_same_theme_activation_readiness.py`

## Baseline Gate

- Current aggregate Space promotion gate passed: `False`
- Gate reason: `insufficient_closed_official_forward_replacement_value`
- Deduped mature 10d closed rows: `18`
- Official/primary mature 10d rows: `13`

## Official Cohort Readout

| Cohort | Rows | Avg same-theme | Median same-theme | Same-theme win | Avg cash | Avg ARKX rel | Avg UFO rel | Top ticker share | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| semantic_bucket=defense_budget_theme | 10 | $0.00 | $160.53 | 50.00% | $1,927.76 | $1,428.36 | $810.07 | 22.10% | fail |
| semantic_bucket=defense_budget_theme / source_type=official_government_release | 10 | $0.00 | $160.53 | 50.00% | $1,927.76 | $1,428.36 | $810.07 | 22.10% | fail |
| source_type=official_government_release | 10 | $0.00 | $160.53 | 50.00% | $1,927.76 | $1,428.36 | $810.07 | 22.10% | fail |
| theme_segment=satellite_connectivity | 6 | $-919.06 | $-1,228.74 | 16.67% | $615.97 | $196.84 | $-266.03 | 45.94% | fail |
| semantic_bucket=defense_budget_theme / source_type=official_government_release / theme_segment=satellite_connectivity | 5 | $-858.33 | $-1,234.75 | 20.00% | $1,069.43 | $570.03 | $-48.26 | 45.94% | fail |
| semantic_bucket=defense_budget_theme / theme_segment=satellite_connectivity | 5 | $-858.33 | $-1,234.75 | 20.00% | $1,069.43 | $570.03 | $-48.26 | 45.94% | fail |
| source_type=official_government_release / theme_segment=satellite_connectivity | 5 | $-858.33 | $-1,234.75 | 20.00% | $1,069.43 | $570.03 | $-48.26 | 45.94% | fail |
| theme_segment=launch_lunar | 4 | $986.46 | $706.44 | 100.00% | $2,549.37 | $2,209.79 | $1,533.95 | 69.94% | fail |
| semantic_bucket=defense_budget_theme / source_type=official_government_release / theme_segment=space_data_defense | 3 | $504.20 | $532.34 | 66.67% | $2,431.96 | $1,932.56 | $1,314.27 | 41.57% | fail |
| semantic_bucket=defense_budget_theme / theme_segment=space_data_defense | 3 | $504.20 | $532.34 | 66.67% | $2,431.96 | $1,932.56 | $1,314.27 | 41.57% | fail |
| source_type=official_government_release / theme_segment=space_data_defense | 3 | $504.20 | $532.34 | 66.67% | $2,431.96 | $1,932.56 | $1,314.27 | 41.57% | fail |
| theme_segment=space_data_defense | 3 | $504.20 | $532.34 | 66.67% | $2,431.96 | $1,932.56 | $1,314.27 | 41.57% | fail |

## Gate 4

```json
{
  "acceptance_rule": "Observed-only pass requires at least one production-visible official/primary Space cohort with >=5 closed mature 10d rows, avg 10d same-theme replacement value > $0.01, median >= 0, same-theme win rate >= 50%, avg 10d cash PnL > 0, avg 10d ARKX/UFO relative value > 0, and max single ticker positive PnL share <= 50%; no live slots or trade adapter may change.",
  "activation_blockers": [
    "aggregate_space_promotion_gate_not_passed",
    "production_observation_slot_has_zero_selected_candidates"
  ],
  "failed_reasons": [
    "no_official_cohort_passed_same_theme_replacement_gate"
  ],
  "passed": false,
  "passing_cohorts": [],
  "promotion_grade": false,
  "status": "rejected",
  "strategy_behavior_changed": false
}
```

## Production Impact

No shared policy, backtester adapter, run adapter, live slot, ranking, sizing, exit, LLM/news, or order behavior changed.

No JavaScript was used.
