# exp-20260512-025 SEC financial-report 10-Q queue priority

- Decision: `rejected_10q_queue_priority`
- EV delta: `0.416228`
- Total PnL delta: `14430.16`
- Sleeve PnL delta: `14430.16`
- Changed closed trades: `10`

## Aggregate

| Variant | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |
| --- | ---: | ---: | ---: | ---: | ---: |
| t1_excess_desc | 8.558004 | $234,762.79 | $48,332.18 | 52 | 0.1007 |
| tenq_first_then_t1_excess | 8.974232 | $249,192.95 | $62,762.34 | 52 | 0.0934 |

## Window Deltas

| Window | EV delta | PnL delta | Sleeve PnL delta | Changed trades | Max DD delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| late_strong | -0.026341 | $-416.95 | $-416.95 | 4 | -0.000123 |
| mid_weak | 0.000000 | $0.00 | $0.00 | 0 | 0.000000 |
| old_thin | 0.442569 | $14,847.11 | $14,847.11 | 6 | -0.007345 |

This is a default-off paper sleeve candidate-ranking alpha experiment. It changes no live orders, queue qualification, capacity, hold days, notional, or core signal path.
