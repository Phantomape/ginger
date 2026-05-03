# Form 4 Insider Overlay Duplicate Guardrail

- experiment_id: `exp-20260503-020`
- timestamp: `2026-05-03T09:04:13+00:00`
- decision: `data_gap`
- production_impact: `data_audit_only`

## Hypothesis

Public-market open-market insider Form 4 buying may confirm existing trend_long/breakout_long candidates, but this run only checks whether new PIT-safe transaction-level data arrived after the prior Form 4 audit.

## Historical Experiment Check

- Exact prior experiment: `exp-20260503-017`.
- Prior decision: `data_gap`.
- Prior result: 0 daily Form 4 archive items, 0 transaction-level XML rows, 0 PIT-safe meaningful insider-buy candidates, and no measurable slot value.
- New local PIT-safe Form 4 evidence since prior: `false`.
- This is not a simple rerun because it only checks whether new data exists before repeating the same zero-row shadow overlay.

## Data Availability / PIT Status

- CIK mapping remains usable: core 43/45, pilot 3/3, observation 13/13.
- Archived news Form 4 items remain 0.
- Submission cache Form 4 metadata rows remain 34738, but this cache is latest-snapshot metadata, not PIT-safe transaction evidence.
- Missing transaction fields remain: transaction date, officer title, role flags, transaction code, shares, price, transaction value, ownership nature, 10b5-1 flag, option exercise flag, open-market purchase flag, usable trade date, and PIT-safe flag.

## Shadow Overlay Metrics

- meaningful insider-buy candidate_count: 0
- overlap_with_existing_signals: 0
- scarce-slot opportunity cost: not measurable
- forward 5/10/20/60/90d return of tagged candidates: no sample
- expected_value_score_delta: 0.0

## Decision

`data_gap`. Do not promote Form 4 overlay, do not infer alpha from static Form 4 metadata, and do not rerun this same shadow test until transaction-level PIT rows exist.

## Next Minimum Action

Build a default-off append-only Form 4 adapter for SEC owner=include type=4 feeds and transaction XML parsing; rerun shadow tagging only after nonzero PIT-safe open-market purchase rows accumulate.
