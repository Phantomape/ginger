# exp-20260511-022 Space Non-Data-Vendor Breakout Risk

Decision: `rejected_non_data_vendor_breakout_risk_haircut`.
Fixed before state: official-catalyst Space `0.75x` plus PL/BKSY `breakout_long` `0.25x` haircut plus RKLB/ASTS `trend_long` `1.25x` top-up.
Best non-data-vendor breakout scalar: `0.25`.

## Sweep

| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows |
|---:|---|---:|---:|---:|---:|
| 0.75 | fail | +0.0667 | -150.62 | +0.0178 | 1/3 |
| 0.5 | fail | +0.1286 | -386.28 | +0.0189 | 1/3 |
| 0.25 | fail | +0.2184 | -44.75 | +0.0201 | 1/3 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Adjusted signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.7471 | 4.7471 | +0.0000 | +0.5131 | 102533.13 | 102533.13 | +0.00 | 4 |
| mid_weak | 3.0517 | 3.3404 | +0.2887 | +1.6715 | 79675.53 | 83931.95 | +4256.42 | 11 |
| old_thin | 0.6919 | 0.6216 | -0.0703 | +0.2363 | 44928.42 | 40627.25 | -4301.17 | 6 |

Gate 4: `failed`.

Interpretation: Do not haircut non-data-vendor Space breakouts on this frozen sample. The accepted data-vendor haircut is not transferable to RKLB/ASTS/RDW/LUNR-style breakout entries without stronger forward evidence.

Production impact: replay-only alpha search; no shared policy, run adapter, order, ranking, signal generation, or live sizing behavior changed.
