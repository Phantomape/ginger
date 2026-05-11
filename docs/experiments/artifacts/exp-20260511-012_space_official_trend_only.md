# exp-20260511-012 Space Official-Catalyst Trend-Only Refinement

Decision: `rejected_trend_only_refinement`.

Hypothesis: keep the accepted official-catalyst Space pool and 0.75x risk budget, but allow only `trend_long` Space entries.

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Removed Space signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4465 | 4.6735 | +0.2270 | +0.4395 | 97942.41 | 100939.24 | +2996.83 | 3 |
| mid_weak | 2.7096 | 2.3011 | -0.4085 | +0.6322 | 73829.93 | 73985.20 | +155.27 | 8 |
| old_thin | 0.6919 | 0.5662 | -0.1257 | +0.1809 | 44928.42 | 39867.12 | -5061.30 | 6 |

Gate 4: `failed`.

Interpretation: The accepted Space sleeve should not remove breakout_long entries from the frozen official-catalyst hypothesis. Breakout losses are visible, but a broad strategy-family exclusion gives up too much expected value versus the current 0.75x hypothesis.

Production impact: replay-only alpha search. No orders, core ranking, sizing, live slots, LLM prompt, or production adapter changed.
