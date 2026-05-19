# exp-20260512-034 SEC auxiliary earnings 8-K notional

- decision: `rejected_auxiliary_earnings8k_notional_scalar`
- changed_variable: `sec_financial_report_auxiliary_earnings8k_notional_scalar`
- best_variant: `auxiliary_earnings8k_scalar_1.50`
- expected_value_score_delta: `0.011188`
- total_pnl_delta: `375.44`
- sleeve_pnl_delta: `375.44`
- gate_passed: `False`

## Window Deltas

| window | EV delta | PnL delta | Max DD delta | Aux 8-K trades | Aux 8-K PnL delta |
|---|---:|---:|---:|---:|---:|
| late_strong | 0.054547 | 1139.48 | 3e-05 | 5 | 1139.47 |
| mid_weak | -0.024809 | -241.44 | 0.0 | 1 | -241.44 |
| old_thin | -0.01855 | -522.6 | 0.002148 | 5 | -522.59 |

## Interpretation

Do not retry auxiliary earnings 8-K notional scalars on this frozen sample; future SEC work needs forward outcomes or a genuinely new earnings-quality field.
