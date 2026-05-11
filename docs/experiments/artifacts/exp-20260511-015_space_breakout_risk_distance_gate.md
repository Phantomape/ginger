# exp-20260511-015 Space Breakout Risk-Distance Gate

Decision: `rejected_breakout_risk_distance_refinement`.
Best cap: `10%`.

## Sweep

| Max initial risk | Gate | dEV vs before | dPnL vs before | dDD vs before | dDD vs core | EV improved windows |
|---:|---|---:|---:|---:|---:|---:|
| 0.08 | fail | -0.3072 | -1909.20 | +0.0429 | +0.0517 | 1/3 |
| 0.09 | fail | -0.5026 | -1473.45 | +0.0429 | +0.0197 | 0/3 |
| 0.1 | fail | +0.0000 | +0.00 | +0.0000 | +0.0197 | 0/3 |
| 0.12 | fail | +0.0000 | +0.00 | +0.0000 | +0.0197 | 0/3 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Removed Space signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4465 | 4.4465 | +0.0000 | +0.2125 | 97942.41 | 97942.41 | +0.00 | 1 |
| mid_weak | 2.7096 | 2.7096 | +0.0000 | +1.0407 | 73829.93 | 73829.93 | +0.00 | 1 |
| old_thin | 0.6919 | 0.6919 | +0.0000 | +0.3066 | 44928.42 | 44928.42 | +0.00 | 3 |

Gate 4: `failed`.

Interpretation: Space breakout losses are visible, but a simple entry-to-stop distance cap is not a robust enough refinement over the accepted 0.75x official catalyst hypothesis.

Production impact: replay-only alpha search. No orders, core ranking, sizing, live slots, LLM prompt, or production adapter changed by this script.
