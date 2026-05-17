# exp-20260516-045 SEC cash-flow forecast notional

- decision: `rejected_cash_flow_forecast_notional_scalar`
- changed_variable: `sec_financial_report_cash_flow_forecast_notional_scalar`
- best_variant: `cash_flow_forecast_scalar_0.50`
- expected_value_score_delta: `0.046961`
- total_pnl_delta: `-395.04`
- sleeve_pnl_delta: `-239.74`
- gate_passed: `False`
- cash_flow_forecast_present_rate: `0.1389`

## Window Deltas

| window | EV delta | PnL delta | Max DD delta | Field trades | Field PnL delta |
|---|---:|---:|---:|---:|---:|
| late_strong | 0.067468 | 15.84 | -7e-06 | 4 | 15.82 |
| mid_weak | -0.016612 | -269.34 | 0.000228 | 1 | -269.33 |
| old_thin | -0.003895 | -141.54 | -0.002235 | 3 | -141.54 |

## Interpretation

Do not retry cash-flow forecast notional scalars on this frozen sample; future SEC completeness work needs broader production-visible forecast fields, fuller text coverage, or forward replacement-value evidence.
