# exp-20260512-033 SEC financial-report paired-filing dedupe

- Decision: `rejected_paired_filing_dedupe`
- Best tested dedupe variant: `keep_10q_else_periodic`
- EV delta: `-0.332425`
- Total PnL delta: `1271.12`
- Sleeve PnL delta: `1581.71`
- Deduped candidates: `19`

## Aggregate

| Variant | EV sum | EV delta | Total PnL | Total PnL delta | Sleeve PnL | Sleeve closed | Max DD max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | 8.558004 | 0.000000 | $234,762.79 | $0.00 | $48,332.18 | 52 | 0.1007 |
| keep_10q_else_periodic | 8.225579 | -0.332425 | $236,033.91 | $1,271.12 | $49,913.89 | 50 | 0.0985 |
| keep_earnings_8k | 7.400206 | -1.157798 | $217,056.47 | $-17,706.32 | $31,247.05 | 50 | 0.1034 |
| keep_highest_t1_excess | 8.225579 | -0.332425 | $236,033.91 | $1,271.12 | $49,913.89 | 50 | 0.0985 |

## Window Deltas For keep_10q_else_periodic

| Window | Deduped | EV delta | PnL delta | Sleeve PnL delta | Changed trades | Max DD delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 7 | -0.420478 | $-5,229.28 | $-5,229.28 | 3 | 0.001213 |
| mid_weak | 5 | -0.137289 | $-2,249.61 | $-1,939.02 | 1 | 0.000000 |
| old_thin | 7 | 0.225342 | $8,750.01 | $8,750.01 | 6 | -0.002243 |

This is a default-off paper sleeve candidate-pool alpha experiment. It changes no live orders, queue qualification, capacity, hold days, notional, or core signal path.
