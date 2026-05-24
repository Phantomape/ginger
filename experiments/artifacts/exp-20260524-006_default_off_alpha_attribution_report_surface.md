# exp-20260524-006 Default-Off Alpha Attribution Report Surface

Decision: `accepted_measurement_repair_no_strategy_change`.

## Change

Add `default_off_alpha_attribution` as a read-only rollup across pilot, SEC financial-report, event bundle, state-surface, ETF, core-misfit, and broad-market paper sleeves; wire it into `run.py` artifacts and the daily human report.

## Validation

- `.venv\Scripts\python.exe -B -m py_compile quant\default_off_alpha_attribution.py quant\report_generator.py quant\run.py`
- `.venv\Scripts\python.exe -B -m pytest quant\test_default_off_alpha_attribution.py quant\test_pilot_sleeve.py`

## Sample Surface

- surface_count: `7`
- status_counts: `{'blocked': 2, 'eligible_for_review': 1, 'inactive': 4}`
- eligible_for_separate_activation_review: `['broad_market_leadership']`
- top_blockers: `[{'reason': 'missing_forward_gate', 'count': 4, 'surfaces': ['core_misfit_paper', 'event_overlay_bundle', 'low_deployment_etf_overlay', 'sec_financial_report_t1']}, {'reason': 'closed_pilot_outcomes', 'count': 1, 'surfaces': ['ai_infra_aggressive']}, {'reason': 'min_closed_trades', 'count': 1, 'surfaces': ['state_surface_satellite']}]`

No JavaScript was used.
