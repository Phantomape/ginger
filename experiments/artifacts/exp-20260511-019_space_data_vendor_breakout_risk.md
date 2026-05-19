# exp-20260511-019 Space Data-Vendor Breakout Risk

Decision: `accepted_default_off_data_vendor_breakout_risk_haircut`.
Best data-vendor breakout scalar: `0.25`.

## Sweep

| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows |
|---:|---|---:|---:|---:|---:|
| 0.75 | pass | +0.0768 | +1168.79 | +0.0197 | 2/3 |
| 0.5 | pass | +0.1752 | +2452.26 | +0.0197 | 2/3 |
| 0.25 | pass | +0.2741 | +3774.55 | +0.0197 | 2/3 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4465 | 4.6211 | +0.1746 | +0.3871 | 97942.41 | 100235.60 | +2293.19 | 1 |
| mid_weak | 2.7096 | 2.8091 | +0.0995 | +1.1402 | 73829.93 | 75311.29 | +1481.36 | 2 |
| old_thin | 0.6919 | 0.6919 | +0.0000 | +0.3066 | 44928.42 | 44928.42 | +0.00 | 1 |

Gate 4: `passed`.

Interpretation: The accepted Space official-catalyst sleeve improves when PL/BKSY breakout entries keep eligibility but receive an extra 0.25x risk haircut. This refines the default-off forward hypothesis only; live Space slots remain zero.

Production impact: accepted as shared default-off Space sleeve metadata/helper. Live Space slots remain zero; no orders, core ranking, signal generation, or live sizing path changed. Daily Space snapshot/report now expose the same PL/BKSY breakout `0.25x` hypothesis before any future trade-enabled adapter.
