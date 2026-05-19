# exp-20260512-020 SEC financial-report 10-Q notional

- Decision: `accepted_10q_periodic_report_notional_2.00x`
- Best variant: `tenq_scalar_2.00`
- EV delta: `0.452561`
- Total PnL delta: `9227.36`
- Max drawdown delta max: `0.004222`
- 10-Q closed trades after: `12`

## Aggregate

| Variant | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |
| --- | ---: | ---: | ---: | ---: | ---: |
| tenq_scalar_0.75 | 7.779671 | $219,383.85 | $33,341.49 | 52 | 0.0949 |
| tenq_scalar_1.00 | 7.944809 | $222,459.65 | $36,339.63 | 52 | 0.0951 |
| tenq_scalar_1.25 | 8.105443 | $225,535.43 | $39,337.77 | 52 | 0.0965 |
| tenq_scalar_1.50 | 8.261314 | $228,611.21 | $42,335.90 | 52 | 0.0979 |
| tenq_scalar_1.75 | 8.412220 | $231,687.00 | $45,334.03 | 52 | 0.0993 |
| tenq_scalar_2.00 | 8.558004 | $234,762.79 | $48,332.18 | 52 | 0.1007 |

## Window Deltas

| Window | EV delta | PnL delta | 10-Q PnL delta | Max DD delta |
| --- | ---: | ---: | ---: | ---: |
| late_strong | 0.101014 | $2,084.72 | $2,084.72 | -0.000752 |
| mid_weak | 0.289207 | $4,785.01 | $4,785.01 | -0.000830 |
| old_thin | 0.062340 | $2,357.63 | $2,357.63 | 0.004222 |

This is a semantic default-off paper sleeve risk-allocation experiment. It changes no live orders, queue qualification, candidate ranking, capacity, or hold period.
