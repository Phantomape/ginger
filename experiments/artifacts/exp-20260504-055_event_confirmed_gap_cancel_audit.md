# exp-20260504-055 Event-Confirmed Gap-Cancel Audit

## Result

Rejected before implementation. The frozen exp-20260504-049 event bundle has zero active-window overlap with A/B upside gap-cancel candidates in all three canonical windows.

| window | baseline EV | baseline PnL | trades | survival | gap_cancel candidates | event trades | active event matches |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 78600.33 | 19 | 0.8039 | 4 | 12 | 0 |
| mid_weak | 1.4415 | 55015.08 | 21 | 0.7925 | 4 | 15 | 0 |
| old_thin | 0.3179 | 24642.07 | 22 | 0.9167 | 5 | 8 | 0 |

## Decision

- Do not add an event-confirmed upside-gap exception now.
- Do not retune the gap threshold, event thresholds, event holding period, or event notional from this result.
- A future retry needs a broader PIT-safe event candidate surface that overlaps skipped A/B candidates before any policy code change.
