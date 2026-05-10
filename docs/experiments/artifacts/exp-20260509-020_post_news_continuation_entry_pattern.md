# exp-20260509-020 Post-News Continuation Entry Pattern

Decision: `rejected_positive_but_immaterial`

## Rule

Shadow PEAD-like satellite: high-confidence `8k_item_2_02` event, event-day close-to-close reaction > 1.0%, event-day volume >= 1.5x prior 20-day average, enter next open, exit on the 10th trading day after the event, fixed $10,000 notional, max 5 active positions.

## Three-Window Result

| Window | Core EV | Variant EV | Delta EV | Core PnL | Variant PnL | Delta PnL | Event trades | Event PnL | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.0166 | -0.0508 | $90,788.88 | $91,494.51 | $+705.63 | 13 | $+23.63 | 0.3846 |
| mid_weak | 1.6195 | 1.8603 | +0.2408 | $59,540.63 | $63,927.58 | $+4,386.95 | 22 | $+4,325.78 | 0.5909 |
| old_thin | 0.3583 | 0.4163 | +0.0580 | $27,347.42 | $30,384.63 | $+3,037.21 | 20 | $+3,037.21 | 0.65 |

## Aggregate

- EV sum: 6.0452 -> 6.2932 (+0.2480, +4.10%)
- PnL sum: $177,676.93 -> $185,806.72 (+8,129.79, +4.58%)
- EV windows improved/regressed: 2/1

## Decision Rationale

Rejected for production promotion. The PEAD-like post-news continuation pattern was positive in aggregate but did not clear Gate 4 materiality: the late_strong window was effectively flat while aggregate PnL/EV improvement was below the required threshold.

## Production Impact

No production orders, shared core policy, sizing, ranking, exits, LLM/news prompt, or live universe changed. A positive retry would need a shared default-off post-news sleeve adapter before any promotion.
