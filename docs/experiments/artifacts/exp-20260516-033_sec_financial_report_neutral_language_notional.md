# exp-20260516-033 SEC neutral-language notional

- decision: `rejected_neutral_language_notional_scalar`
- changed_variable: `sec_financial_report_neutral_language_notional_scalar`
- best_variant: `neutral_language_scalar_2.00`
- expected_value_score_delta: `0.502294`
- total_pnl_delta: `19499.77`
- sleeve_pnl_delta: `19189.18`
- gate_passed: `False`
- text_coverage_rate: `0.5926`

## Window Deltas

| window | EV delta | PnL delta | Max DD delta | Neutral trades | Neutral PnL delta |
|---|---:|---:|---:|---:|---:|
| late_strong | -0.194157 | 100.57 | 0.000572 | 8 | 127.6 |
| mid_weak | 0.320352 | 4982.83 | -0.001698 | 4 | 4982.84 |
| old_thin | 0.376099 | 14416.37 | 0.006251 | 9 | 14416.37 |

## Interpretation

Do not retry neutral-language notional scalars on this frozen sample; future SEC text work needs production-visible language fields, fuller text coverage, or forward replacement-value evidence.
