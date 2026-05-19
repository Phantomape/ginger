# exp-20260516-034 SEC guidance-raise notional

- decision: `rejected_guidance_raise_notional_scalar`
- changed_variable: `sec_financial_report_guidance_raise_notional_scalar`
- best_variant: `guidance_raise_scalar_2.50`
- expected_value_score_delta: `0.077989`
- total_pnl_delta: `944.14`
- sleeve_pnl_delta: `944.14`
- gate_passed: `False`
- text_coverage_rate: `0.5926`

## Window Deltas

| window | EV delta | PnL delta | Max DD delta | Guidance trades | Guidance PnL delta |
|---|---:|---:|---:|---:|---:|
| late_strong | 0.0 | 0.0 | 0.0 | 0 | 0.0 |
| mid_weak | 0.077989 | 944.14 | -0.000792 | 1 | 944.13 |
| old_thin | 0.0 | 0.0 | 0.0 | 0 | 0.0 |

## Interpretation

Do not retry guidance-raise notional scalars on this frozen sample without more covered guidance-raise rows, fuller text coverage, or forward replacement-value evidence.
