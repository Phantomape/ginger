# exp-20260511-021 Space Launch/Connectivity Trend Risk

Decision: `accepted_default_off_launch_connectivity_trend_risk_topup`.
Best RKLB/ASTS trend scalar: `1.25`.

## Sweep

| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows |
|---:|---|---:|---:|---:|---:|
| 1.1 | pass | +0.1445 | +2572.43 | +0.0197 | 2/3 |
| 1.25 | pass | +0.3686 | +6661.77 | +0.0197 | 2/3 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Trend top-up signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.6211 | 4.7471 | +0.1260 | +0.5131 | 100235.60 | 102533.13 | +2297.53 | 2 |
| mid_weak | 2.8091 | 3.0517 | +0.2426 | +1.3828 | 75311.29 | 79675.53 | +4364.24 | 4 |
| old_thin | 0.6919 | 0.6919 | +0.0000 | +0.3066 | 44928.42 | 44928.42 | +0.00 | 0 |

Gate 4: `passed`.

Interpretation: Within the accepted Space official-catalyst sleeve, RKLB/ASTS trend_long entries support a 1.25x extra scalar while staying below original pre-Space sizing. This refines the default-off forward hypothesis only; live Space slots remain zero.

Production impact: accepted as shared default-off Space forward-hypothesis metadata/helper. Live Space slots remain zero; no orders, core ranking, signal generation, or live sizing path changed.
