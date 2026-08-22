# exp-20260728-002 — Massive full-market research source contract

## Authorization and permitted use

- The user explicitly attested on 2026-07-27 (America/Los_Angeles) that their
  Massive entitlement permits internal non-display research, backtesting,
  strategy development, and derived-data retention.
- The credential is read from `MASSIVE_API_KEY` or the gitignored
  `secrets/massive.txt`. It must never be written to URLs, logs, exceptions,
  SQLite, manifests, tickets, or artifacts.
- Data and derived artifacts remain local and are not redistributed.

## Source and clocks

- Grouped daily endpoint:
  `GET https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=false`.
- Reference endpoint:
  `GET https://api.massive.com/v3/reference/tickers`, including separate
  active and inactive traversals with an HTTPS `api.massive.com` next-page
  allowlist.
- Each raw response is frozen with retrieval UTC, sanitized request URL,
  SHA-256, exact compressed bytes, normalized rows, and the matching
  checkpoint in one SQLite transaction.
- The simulated daily decision clock may use only the requested market date
  and fields available by that date. Retrieval UTC proves what was tested; it
  does not prove the vendor would have returned the identical payload then.

## PIT classification

```yaml
pit_tier: research_pit
evidence_grade: lead
known_future_leakage: false
requested_use: source_staging_and_later_private_replay_scout
maximum_disposition: observed_only
paper_live_eligible: false
```

`known_future_leakage=false` depends on keeping bars unadjusted and refusing to
use current active status, current mappings, later delisting facts, or later
corporate actions as decision-time features. Active/inactive metadata exists
for coverage and identity audit; later replay must resolve identity as of the
decision date and must not rank on later status.

## Known limitations and canonical upgrade

- The accessible plan begins at 2024-07-29; a 2024-01-03 request returned 403.
  Therefore the first part of `old_thin` has less than a 60-session warm-up.
- Current vendor corrections and immutable historical response vintages are
  not proven.
- Ticker reuse requires an effective-dated stable identity resolver before a
  candidate can be promoted.
- Split normalization must use only split events effective by the simulated
  decision time. Current fully adjusted history is forbidden as an input.
- Canonical promotion requires immutable/as-published vintages or forward
  append-only evidence, effective-dated identity, split/revision semantics,
  and shared replay/daily parity. This experiment does not provide them.

## Production impact

None. The staging database is `data/warehouse/massive_history.sqlite`, separate
from the canonical cold/hot OHLCV warehouse. This experiment does not touch
`quant/run.py`, the backtester, ranking, sizing, exits, orders, open positions,
or `trade_enabled` behavior.
