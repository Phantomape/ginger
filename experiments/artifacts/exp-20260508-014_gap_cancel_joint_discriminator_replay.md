# exp-20260508-014 Gap-Cancel Joint Discriminator Replay

## Decision

- decision: rejected
- best variant: joint_volume_low_sector_rs_high
- production orders changed: false
- shared policy changed: false

## Variant Summary

| Variant | Gate4 | EV Delta Sum | PnL Delta | PnL Delta % | Positive EV Windows | Negative EV Windows | DD >1pp Worse | Bypasses |
|---|---:|---:|---:|---:|---|---|---|---:|
| joint_volume_low_sector_rs_high | False | +0.1555 | +230.22 | +0.14% | late_strong | mid_weak | none | 3 |
| joint_gap_gt5_sector_rs_high | False | +0.0541 | +1790.04 | +1.07% | mid_weak | none | none | 1 |
| joint_sector_rs_high_low_8k | False | -0.1055 | -2017.27 | -1.21% | mid_weak | late_strong | none | 4 |
| joint_bbwidth_high_low_8k | False | -0.1315 | -3523.41 | -2.11% | none | late_strong, mid_weak | none | 2 |
| gap_abs_high | False | -0.8509 | -21476.26 | -12.83% | mid_weak, old_thin | late_strong | none | 7 |
| gap_bucket_4_5 | False | -0.9136 | -23713.29 | -14.17% | none | late_strong, mid_weak | none | 4 |

## Best Variant Window Metrics

| Window | EV Before | EV After | EV Delta | Sharpe Delta | DD Delta | PnL Delta | Trades Delta | Bypasses |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.7435 | 3.9453 | +0.2018 | +0.0900 | +0.0000 | +2768.54 | +2 | 2 |
| mid_weak | 1.5478 | 1.5015 | -0.0463 | +0.0400 | +0.0000 | -2538.32 | +0 | 1 |
| old_thin | 0.3359 | 0.3359 | +0.0000 | +0.0000 | +0.0000 | +0.00 | +0 | 0 |

## Production Parity

No executable policy was promoted. A future positive retry must move the discriminator into a shared production/backtest policy before it can affect live orders.

