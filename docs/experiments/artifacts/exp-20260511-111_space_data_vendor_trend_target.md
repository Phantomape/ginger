# exp-20260511-111 Space Data-Vendor Trend Target

Decision: `rejected_data_vendor_trend_target_extension`

Single variable: PL/BKSY trend_long target ATR multiple inside the default-off official Space sleeve.

| Variant | Window | EV | EV delta vs accepted | PnL delta vs accepted | Trades | Max DD | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted_exp105_stack | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| accepted_exp105_stack | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| accepted_exp105_stack | old_thin | 0.7694 | +0.0000 | +0.00 | 24 | 0.1012 | 0.8919 |
| data_vendor_trend_target_6_0 | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| data_vendor_trend_target_6_0 | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| data_vendor_trend_target_6_0 | old_thin | 0.4466 | -0.3228 | -13,201.24 | 24 | 0.1012 | 0.8919 |
| data_vendor_trend_target_7_0 | late_strong | 4.9509 | +0.0000 | +0.00 | 23 | 0.0629 | 0.8070 |
| data_vendor_trend_target_7_0 | mid_weak | 4.2199 | +0.0000 | +0.00 | 26 | 0.0471 | 0.8169 |
| data_vendor_trend_target_7_0 | old_thin | 0.4466 | -0.3228 | -13,201.24 | 24 | 0.1012 | 0.8919 |

## Best Variant

- Best variant: `data_vendor_trend_target_6_0`
- Aggregate EV delta vs accepted: `-0.3228`
- Aggregate PnL delta vs accepted: `$-13,201.24`
- Gate 4 passed: `False`

## Interpretation

PL/BKSY data-vendor trend target widening did not beat the accepted exp-105 Space stack under the three-window gate. The current evidence supports keeping data-vendor trend targets at the broad 5 ATR official Space setting.

## Production Impact

Default-off Space metadata experiment. Live Space slots remain zero; no core production orders, ranking, sizing, or signal generation changed.
