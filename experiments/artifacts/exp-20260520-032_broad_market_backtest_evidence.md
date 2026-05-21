# exp-20260520-032 cien_technology_haircut_exception_reference_v1

Decision: `rejected_existing_backtest_single_trade_concentration`.

## Hypothesis

A broad-market leadership candidate can replace overly blunt sector haircuts only if the effect survives multi-window replay without single-trade dependence.

## Trial Accounting

- mechanism_family: `broad_market_forward_maturation`
- trial_family: `broad_market_leadership_forward_maturation`
- changed_variable: `technology_haircut_exception_for_cien`
- prior_trial_count: `17`
- multiple_testing_risk_bucket: `low`

## Metric Evidence

```json
{
  "after_aggregate": {
    "cien_selected_trade_count": 1,
    "expected_value_score": 8.3175,
    "total_pnl": 250987.67,
    "trade_count": 61
  },
  "baseline_experiment": "exp-20260520-021",
  "before_aggregate": {
    "expected_value_score": 7.8941,
    "total_pnl": 234850.99,
    "trade_count": 61
  },
  "decision": "rejected_and_rolled_back",
  "delta_aggregate": {
    "expected_value_score": 0.4234,
    "total_pnl": 16136.68,
    "trade_count": 0
  },
  "evidence_type": "canonical_three_window_backtest",
  "gate_assessment": {
    "gate_1_baseline": "pass",
    "gate_2_fields": "pass",
    "gate_3_survival_rate": "pass",
    "gate_4": "fail",
    "reason": "The improvement is entirely explained by one CIEN trade in one window. That confirms a potential mechanism conflict but is too sample-thin and ticker-specific for live core promotion."
  },
  "rejection_reason": "Positive aggregate result is a single-trade CIEN contribution in mid_weak only; high multiple-testing and ticker-specific exception risk. Keep as paper/default-off sleeve candidate rather than production core rule.",
  "selected_trade_count": 1,
  "source_artifact": "data/experiments/exp-20260520-022/cien_technology_haircut_exception_summary.json",
  "source_experiment": "exp-20260520-022"
}
```

## Next Evidence Needed

Collect broader closed replacement-value outcomes beyond one CIEN trade before any core exception.
