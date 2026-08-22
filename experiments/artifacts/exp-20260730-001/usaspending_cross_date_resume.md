# exp-20260730-001 — USAspending cross-date receipt drain

## Decision

Accept as a measurement repair. The change restores an irreplaceable forward-observer calendar contract and does not change signals, ranking, sizing, exits, orders, or `trade_enabled`.

## Observed fault

The real producer journal still held a validated `2026-07-29` USAspending job after the UTC date boundary. It remained `running` after 15 status polls. The accepted same-day resume implementation filtered continuation through the caller's new run date, so a `2026-07-30` invocation could skip the valid old receipt, submit a duplicate job, and lose the old calendar snapshot. The central dated non-OHLCV snapshot also did not durably contain the already-computed USAspending health entry.

## Repair contract

- Validate and drain the single TTL-valid receipt using its frozen original run date and request before any current-day POST.
- If the old job is still pending, return its old run date and block the current-day POST.
- If the old job finishes, freeze and consume its snapshot under the old run date, persist a verifiable `completed` journal, and only then attempt the current day.
- Treat invalid, expired, future-dated, or unverifiable receipt state as fail-closed with no network fallback.
- Persist the existing producer-health coverage entry into the dated non-OHLCV daily snapshot.

## Verification

- Producer fixture suite: 36 passed.
- USAspending daily-wiring slice: 8 passed.
- Full producer plus daily-wiring regression: 103 passed.
- Python compilation and `git diff --check`: passed.
- Gate-1 identity remains `4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731` with aggregate EV 6.2057, PnL 130,992.36, 49 trades, minimum survival 81.16%, and worst drawdown 8.89%.
- No live network call, order attempt, strategy mutation, or production observer-state write was made during verification.

## Remaining field check

The next scheduled daily run must confirm that the real `2026-07-29` receipt is either still represented as a blocking pending job or is consumed once under its original date before the current-day request, and that the dated daily snapshot exposes the producer-health entry. This is field validation of an accepted deterministic contract, not a new alpha experiment.
