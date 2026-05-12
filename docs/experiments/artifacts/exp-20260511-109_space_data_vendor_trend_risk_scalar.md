# exp-20260511-109 Space Data-Vendor Trend Risk Scalar

Decision: `rejected_data_vendor_trend_risk_scalar`

Single variable: PL/BKSY trend_long extra risk scalar inside the default-off official Space sleeve.

| Variant | Window | EV | EV delta vs accepted | PnL delta vs accepted | Trades | Max DD | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_exp105_stack | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| accepted_exp105_stack | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| accepted_exp105_stack | old_thin | 0.7694 | +0.0000 | +0.00 | 24 | 0.1012 | 0.8919 |
| data_vendor_trend_0_75 | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| data_vendor_trend_0_75 | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| data_vendor_trend_0_75 | old_thin | 0.7107 | -0.0587 | -2,248.20 | 24 | 0.1012 | 0.8919 |
| data_vendor_trend_1_25 | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| data_vendor_trend_1_25 | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| data_vendor_trend_1_25 | old_thin | 0.8303 | +0.0609 | +2,222.16 | 24 | 0.1012 | 0.8919 |
| data_vendor_trend_1_50 | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| data_vendor_trend_1_50 | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| data_vendor_trend_1_50 | old_thin | 0.8930 | +0.1236 | +4,440.80 | 24 | 0.1012 | 0.8919 |

## Best Variant

- Best variant: `data_vendor_trend_1_50`
- Aggregate EV delta vs accepted: `+0.1236`
- Aggregate PnL delta vs accepted: `$+4,440.80`
- Gate 4 passed: `False`

## Interpretation

PL/BKSY data-vendor trend risk scaling did not beat the accepted exp-105 Space stack under the three-window gate. Keep data-vendor trend_long exposure at the accepted default Space risk scalar.

## Production Impact

Default-off Space metadata experiment. Live Space slots remain zero; no core production orders, ranking, or signal generation changed.
