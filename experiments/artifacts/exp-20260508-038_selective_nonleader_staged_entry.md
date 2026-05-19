# exp-20260508-038 selective nonleader staged entry

## Hypothesis

Only stage A/B entries that are not SPY relative leaders. This keeps the accepted relative-strength leader behavior intact while testing whether weaker entries benefit from 75% initial sizing plus the existing day-2 follow-through top-up path.

## Result

- Decision: `rejected_no_effect`
- Rejection reason: No executed positive-share A/B entries qualified as non-SPY-relative leaders; the experiment had zero coverage and left all three-window metrics unchanged.
- Production impact: no promoted strategy change; replay-only experiment artifact.

## Three-window metrics

| Window | EV before | EV after | EV delta | PnL delta | Trades delta | Staged signals |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.0674 | 0.0000 | 0.00 | 0 | 0 |
| mid_weak | 1.6195 | 1.6195 | 0.0000 | 0.00 | 0 | 0 |
| old_thin | 0.3583 | 0.3583 | 0.0000 | 0.00 | 0 | 0 |

## Mechanism note

The selective discriminator had zero coverage: every executed positive-share A/B entry in the canonical windows was already tagged as `spy_relative_leader`. This means the proposed non-leader staged-entry refinement is inert on the current accepted candidate set and should not be retried without new candidate coverage evidence.

## Do not repeat

Do not retry nearby non-leader staged-entry fractions on the same snapshots. The blocker is coverage, not the exact stage fraction.
