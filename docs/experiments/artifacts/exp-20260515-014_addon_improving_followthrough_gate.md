# exp-20260515-014 Add-on Improving-Followthrough Gate

Decision: `rejected_addon_improving_followthrough_gate`.

Single variable: `ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH=True` for the first follow-through add-on. No entry, exit, ranking, candidate, base sizing, cap, heat, slot, LLM, news, Space, or event-sleeve logic changed.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Add-ons before | Add-ons after | Rejected add-ons |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0322 | 5.0322 | +0.0000 | $114,886.19 | $114,886.19 | $+0.00 | 4 | 4 | 0 |
| mid_weak | 1.9947 | 1.9766 | -0.0181 | $72,796.75 | $72,136.36 | $-660.39 | 7 | 6 | 1 |
| old_thin | 0.5059 | 0.5059 | +0.0000 | $35,379.65 | $35,379.65 | $+0.00 | 3 | 3 | 0 |

Aggregate EV delta: `-0.0181`.
Aggregate PnL delta: `$-660.39`.

Gate 4 failed because only `mid_weak` changed, and it regressed after one add-on was rejected by the improving-followthrough gate.
