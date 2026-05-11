# exp-20260511-023 Space Remaining Trend Risk Top-Up

Decision: `rejected_remaining_trend_risk_topup`.
Best remaining-trend scalar: `1.5`.

## Sweep

| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows |
|---:|---|---:|---:|---:|---:|
| 1.1 | fail | +0.0447 | +1995.23 | +0.0217 | 1/3 |
| 1.25 | fail | +0.1117 | +4982.49 | +0.0248 | 1/3 |
| 1.5 | fail | +0.2263 | +10047.75 | +0.0298 | 1/3 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Remaining trend signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.7471 | 4.7471 | +0.0000 | +0.5131 | 102533.13 | 102533.13 | +0.00 | 2 |
| mid_weak | 3.0517 | 3.0517 | +0.0000 | +1.3828 | 79675.53 | 79675.53 | +0.00 | 6 |
| old_thin | 0.6919 | 0.9182 | +0.2263 | +0.5329 | 44928.42 | 54976.17 | +10047.75 | 4 |

Gate 4: `failed`.

Interpretation: The remaining official-catalyst trend trades are a useful forward attribution bucket, but the frozen three-window evidence is too thin to add another default-off risk scalar.

Production impact: no shared policy change because Gate 4 failed. Live Space slots remain zero; no orders, ranking, signal generation, or live sizing path changed.
