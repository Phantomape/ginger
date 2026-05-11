# exp-20260511-018 Space Data-Vendor Trend Gate

Decision: `rejected_data_vendor_trend_gate`.

Hypothesis: keep the accepted official-catalyst Space pool and 0.75x risk budget, but allow PL/BKSY entries only when they are `trend_long`.

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Removed data-vendor signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4465 | 4.6735 | +0.2270 | +0.4395 | 97942.41 | 100939.24 | +2996.83 | 1 |
| mid_weak | 2.7096 | 2.0631 | -0.6465 | +0.3942 | 73829.93 | 69695.88 | -4134.05 | 2 |
| old_thin | 0.6919 | 0.6919 | +0.0000 | +0.3066 | 44928.42 | 44928.42 | +0.00 | 1 |

Gate 4: `failed`.

Interpretation: Data-vendor strategy qualification is not strong enough to replace the accepted Space official-catalyst 0.75x hypothesis.

Production impact: replay-only alpha search. If accepted, the forward hypothesis must be promoted through shared Space sleeve metadata/helper code before any future trade-enabled adapter.
