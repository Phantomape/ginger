# exp-20260824-002 — News Pair First-Seen Forward Readiness

Decision: accept the measurement repair; do not accept or activate alpha.

## What changed

- Newly appended structured-news exposure rows freeze one timezone-aware local
  `first_seen_at` and one batch ID. Existing v1 rows remain untouched and are
  explicitly ineligible for the new forward evidence path.
- New rows enter the measurement clock at the first regular U.S. session open
  strictly after `first_seen_at`, never from the source event date.
- A daily, outcome-blind observer checks whether one first-seen batch contains
  both frozen sides (negative long, positive short), disjoint and sufficiently
  diversified tickers, and fresh point-in-time iBorrowDesk coverage for every
  short-side ticker.
- Missing, stale, unavailable, or invalid borrow evidence blocks the batch.
  iBorrowDesk is labeled indicative and never treated as a broker locate.

## Verification

- 97 focused observer and daily-wiring tests passed.
- Outcome fields were deliberately mutated without changing the readiness
  record.
- Repeating the same run appended no second decision and left the latest
  snapshot byte-identical.
- The canonical regression baseline remained the same file and SHA-256:
  `4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731`.
  Expected-value, PnL, trade-count, drawdown, and survival metrics therefore
  have zero delta by construction.

## Boundary and next action

This change emits no signal, paper fill, `OrderIntent`, or order; it changes no
ranking, sizing, exit, capital allocation, or live permission. `trade_enabled`
remains false. A `measurement_ready` batch means only that forward evidence can
be accumulated without the known clock/borrow leak.

Do not read more historical outcome attribution before the registered 1,508
closed negative-row threshold. The next alpha-policy experiment becomes worth
opening only after at least one real `measurement_ready` first-seen batch is
persisted. Forward acceptance still requires at least 20 closed baskets across
10 decision dates, positive net spread after frozen costs and borrow, positive
chronological halves, and no ticker above 40% of absolute gross contribution.
Live eligibility additionally requires an actual broker-locate contract and a
separate user-approved activation review.
