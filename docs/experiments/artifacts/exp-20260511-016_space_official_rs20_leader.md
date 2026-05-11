# exp-20260511-016 Space Official-Catalyst RS20 Leader Gate

Decision: `rejected_rs20_leader_refinement`.

Hypothesis: keep the accepted official-catalyst Space pool and 0.75x risk budget, but require the existing `rs20_entry_state_leader` flag for Space entries.

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Removed Space signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.4465 | 4.4465 | +0.0000 | +0.2125 | 97942.41 | 97942.41 | +0.00 | 0 |
| mid_weak | 2.7096 | 2.7096 | +0.0000 | +1.0407 | 73829.93 | 73829.93 | +0.00 | 0 |
| old_thin | 0.6919 | 0.6919 | +0.0000 | +0.3066 | 44928.42 | 44928.42 | +0.00 | 0 |

Gate 4: `failed`.

Interpretation: RS20 leadership is useful as a broad core sizing feature, but it is not sufficient as a Space sleeve entry gate on the frozen official catalyst sample. Keep the accepted 0.75x hypothesis unchanged.

Production impact: replay-only alpha search. No orders, core ranking, sizing, live slots, LLM prompt, or production adapter changed by this script.
