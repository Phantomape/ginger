# exp-20260505-031 Event Bundle Follow-Through Delay

- decision: `rejected`
- production_impact: `replay_only`
- timestamp: `2026-05-05T21:13:28+00:00`

## Hypothesis

Frozen event-bundle candidates that first close positive and outperform SPY on the original event entry day may be cleaner satellite entries if entered on the next trading day's open.

## Three-Window Result

| Window | Bundle EV | Variant EV | Delta EV | Bundle PnL | Variant PnL | Delta PnL | Bundle events | Variant events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.9085 | 3.5835 | -0.3250 | $85,151.98 | $81,258.40 | $-3,893.58 | 9 / $5,913.43 | 5 / $2,019.84 |
| mid_weak | 1.8932 | 1.8363 | -0.0569 | $63,318.63 | $62,458.96 | $-859.67 | 11 / $8,544.25 | 7 / $7,220.52 |
| old_thin | 0.3489 | 0.3360 | -0.0129 | $26,040.62 | $25,453.85 | $-586.77 | 7 / $1,398.55 | 5 / $811.78 |

## Decision

Rejected: adding one-day positive and SPY-relative follow-through before event-bundle entry regressed EV or PnL in all three canonical windows. The rule filtered some winning event trades and did not improve the older thin tape either.

## Do Not Repeat

Do not retry nearby one-day follow-through or delayed-entry gates on the same frozen event bundle without new forward outcomes or a materially richer semantic event-quality discriminator.

