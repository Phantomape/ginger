# exp-20260507-008: Core Platform Entry Timing

Decision: `rejected`
Best variant: `pullback_limit_3d_0_5atr`

## Aggregate Proxy Gate

| Variant | EV delta | PnL delta | Windows EV +/- | Touched | Filled | DD worsening | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| pullback_limit_3d_0_5atr | -1.6009 | -27754.4 | 0/3 | 11 | 0 | 0.0034 | False |
| pullback_limit_5d_0_5atr | -1.6009 | -27754.4 | 0/3 | 11 | 0 | 0.0034 | False |

## Cohort Read

| Window | Treatment candidates | Treatment entered | Control candidates | Control entered |
|---|---:|---:|---:|---:|
| late_strong | 4 | 2 | 1 | 0 |
| mid_weak | 4 | 3 | 10 | 3 |
| old_thin | 11 | 6 | 10 | 3 |

## Rejection Reason

Best variant `pullback_limit_3d_0_5atr` did not pass the pre-registered proxy gate: EV delta -1.6009 (-0.197104), windows improved/regressed 0/3, filled 0 of 11 touched entries.

## Production Parity

No production policy changed. This replay uses persisted candidate rows and is not a live order path.
