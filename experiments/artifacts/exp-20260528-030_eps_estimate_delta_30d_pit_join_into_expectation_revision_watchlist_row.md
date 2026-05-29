# exp-20260528-030 EPS Estimate Delta 30d PIT Join into Expectation Revision Watchlist Row

Decision: `accepted_measurement_repair_eps_estimate_delta_30d_field`.

Read-only `measurement_repair`. Reconstructs a PIT-safe
`eps_estimate_delta_30d` (and a `eps_estimate_pct_delta_30d`) for each
row of the `exp-20260525-034` expectation revision watchlist by building
a per-ticker `eps_estimate` timeline from
`data/daily/snapshots/earnings/earnings_snapshot_*.json` — the same
upstream source that already feeds the estimate revision ledger. The
enriched rows are written to
`data/experiments/exp-20260528-030/eps_estimate_delta_30d_pit_join_into_expectation_revision_watchlist_row.json`
without modifying the source artifact.

This change does not modify entries, exits, ranking, sizing, LLM/news
inputs, paper sleeves, or live orders. Rule version:
`earnings_snapshot_pit_eps_estimate_delta_30d_v1`.

## Why this experiment exists

`exp-20260527-002` (EPS 7d magnitude) closed `observed_only_data_gap`.
The watchlist artifact published by `exp-20260525-034` shows
`eps_estimate_delta_30d` at **0/700** coverage and
`eps_estimate_delta_7d` at 388/700 (55%). The
`estimate_revision_ledger` stores the 30d field as `null` for every row
in the watchlist window, even though the underlying
`earnings_snapshot_*.json` history records `eps_estimate` for the
watchlist tickers back to early 2025 (38–52 tickers per snapshot, 437
snapshots from 2024-10-02 onward).

The 30d magnitude branch of the expectation-revision alpha line could
not be tested at all because the magnitude field was simply absent. This
repair fills it from data already on disk.

## PIT semantics

`eps_estimate_at(date)` returns the latest snapshot dated `<= date` that
carried a non-null `eps_estimate` for the ticker. We never read a
snapshot dated after the query date, so no future leak is possible.

For each watchlist row:

- `eps_estimate_at_as_of` = `eps_estimate_at(as_of_date)`
- `eps_estimate_at_as_of_minus_30d` = `eps_estimate_at(as_of_date - 30
  calendar days)`
- `eps_estimate_delta_30d` = current − prior (absolute)
- `eps_estimate_pct_delta_30d` = delta / abs(prior), but `None` when
  `abs(prior) < 0.05` (the `PCT_DELTA_PRIOR_FLOOR`) to avoid spurious
  100x-style percentages from near-zero denominators

The 30 calendar-day offset is computed directly from `as_of_date` in
Python, so the result is deterministic and does not depend on the
current trading calendar.

## Gate 1–3

- Gate 1: baseline is the existing `exp-20260525-034` watchlist (700
  rows; 47 primary positive). Before this repair, all 700 rows had a
  null `eps_estimate_delta_30d`.
- Gate 2: `ticker` and `as_of_date` present on every input row.
- Gate 3: not applicable — read-only field derivation, no filter / rerank
  / eligibility change, so survival rate is structurally unaffected.

## Gate 4 acceptance bar: 30d magnitude is now measurable

```json
{
  "all_passed": true,
  "gate4": {
    "name": "primary_positive_delta_30d_resolved",
    "passed": true,
    "primary_positive_rows": 47,
    "primary_positive_resolved_share": 0.8085106382978723,
    "floor": 0.80
  }
}
```

38/47 (80.85%) primary positive rows now carry a non-null absolute
`eps_estimate_delta_30d`, clearing the 0.80 floor.

## Coverage report

```json
{
  "rows_total": 700,
  "primary_positive_rows": 47,
  "delta_30d_coverage": {
    "all_rows": {"present": 528, "ratio": 0.7543},
    "primary_positive_rows": {"present": 38, "ratio": 0.8085}
  },
  "lookup_status_counts": {
    "ok": 528,
    "no_prior_eps_estimate_within_30d_lookback": 172
  }
}
```

Distribution of the resolved 30d delta on primary positive rows: 25
positive revisions, 9 negative, 4 flat (delta 0). Range −81.92 to
+4.08 (the large negative magnitude is a re-stated / wide-scale prior on
a single ticker and is exactly the kind of value the `pct_delta` floor
protects the percentage form against).

## Still-unresolved primary positive rows (9 of 47)

All 9 carry status `no_prior_eps_estimate_within_30d_lookback`:

- RBLX (2026-05-24/25/26), COHR (2026-05-15/18/19/20), SOFI
  (2026-05-20), MTSI (2026-05-15)

These tickers entered the earnings snapshot universe only in early May
2026 (the universe expanded from ~44 to ~58–59 tickers around
2026-05-10), so a 30-calendar-day lookback from a mid/late-May `as_of`
lands before they had an `eps_estimate` recorded. This is a data-history
limitation, not a logic gap; it will self-heal as the snapshot history
deepens.

## Unblocked downstream experiments

- `exp-20260527-002` EPS magnitude — `eps_estimate_delta_30d` is now
  populated for 80.85% of primary positive rows, so the "larger PIT
  revisions beat smaller ones" attribution can re-run with both 7d and
  30d magnitude axes instead of 7d-only at 55% coverage.
- Any future revision-velocity / acceleration work that wants a 30d
  baseline now has a PIT-safe field to anchor on.

## Files touched

- `quant/experiments/exp_20260528_030_eps_estimate_delta_30d_pit_join_into_expectation_revision_watchlist_row.py` (new)
- `quant/test_exp_20260528_030_eps_estimate_delta_30d_pit_join.py` (new, 11 unit tests)
- `data/experiments/exp-20260528-030/eps_estimate_delta_30d_pit_join_into_expectation_revision_watchlist_row.json` (new)
- `experiments/artifacts/exp-20260528-030_eps_estimate_delta_30d_pit_join_into_expectation_revision_watchlist_row.md` (this file)
- `experiments/logs/exp-20260528-030.json`,
  `experiments/tickets/exp-20260528-030.json`,
  `docs/experiment_log.jsonl`, `docs/experiment_registry.json`

No JavaScript was used.
