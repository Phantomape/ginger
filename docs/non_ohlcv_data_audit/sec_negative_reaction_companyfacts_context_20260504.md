# exp-20260504-014: SEC negative reaction Companyfacts context

## Decision

- Status: rejected
- Decision: rejected_no_companyfacts_discriminator
- Rationale: All events joined only to latest-prior Companyfacts, so the context is stale relative to the 8-K reaction date.

## Three-window baseline

| Window | EV | Sharpe daily | Max DD | PnL | Win rate | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.4191 | 4.35 | 5.41% | $78,600.33 | 78.95% | 19 | 80.39% |
| mid_weak | 1.4415 | 2.62 | 8.79% | $55,015.08 | 52.38% | 21 | 79.25% |
| old_thin | 0.3179 | 1.29 | 8.05% | $24,642.07 | 40.91% | 22 | 91.67% |

Core metrics are unchanged because this is a shadow attribution experiment only.

## Packet summary

- Events: 16; valid 10d: 14; avg 10d excess: 5.733793%; positive 10d rate: 0.642857
- Companyfacts source coverage: 0 same-accession, 16 latest-prior.

## Bucket results

| Bucket | Events | Valid 10d | Avg 10d excess | Positive 10d | Windows |
|---|---:|---:|---:|---:|---|
| fundamental_pressure | 4 | 3 | 16.027467% | 1.0 | {"late_strong": 1, "mid_weak": 2, "old_thin": 1} |
| pressure_but_not_terminal | 12 | 11 | 2.926427% | 0.545455 | {"late_strong": 4, "mid_weak": 5, "old_thin": 3} |

## Production impact

No production order, ranking, sizing, signal generation, or backtester adapter changed.

## Next retry condition

Retry only after PIT-safe same-accession or same-day earnings XBRL snapshots exist for SEC reaction events.
