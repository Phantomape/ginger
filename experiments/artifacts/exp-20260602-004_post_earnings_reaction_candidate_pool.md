# exp-20260602-004: Post-Earnings Reaction Candidate Pool

- Decision: `rejected_post_earnings_reaction_candidate_pool`
- Changed variable: `post_earnings_reaction_candidate_source_v1`
- Baseline: `exp-20260602-003` canonical current core after artifacts
- JavaScript: not used

## Gate 4 Summary

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Aggregate EV | 7.8941 | 7.8941 | +0.0000 |
| Aggregate PnL | $234,850.99 | $234,850.99 | $0.00 |
| Max drawdown ceiling | 11.19% | 11.19% | +0.00% |
| Min survival rate | 79.25% | 79.25% | +0.00% |

## Three Windows

| Window | EV before | EV after | EV delta | PnL delta | Target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $0.00 | 0 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $0.00 | 0 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $0.00 | 0 |

## Gate 2

- Open-position field audit passed: `True`
- Runtime fields: exact-day earnings snapshot, exact OHLCV rows, SPY OHLCV rows, next-open entry, ten-trading-day close exit.

## Production Parity

No production or shared adapter behavior changed. This replay uses the newly accepted post-earnings continuation semantics as the future adapter boundary, but keeps the result default-off and replay-only. A positive result still requires a shared adapter that consumes `post_earnings_continuation_confirmed_v1` directly.

## Interpretation

The post-earnings reaction candidate source did not clear Gate 4. Do not promote it or retry nearby event-day return, close-location, or RS thresholds on these frozen windows without forward rows or a materially richer event-quality field.
