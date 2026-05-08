# exp-20260508-006 Earnings Next-Date Repair Audit

## Hypothesis

Estimate-revision shadow alpha needs a stable same-event key. Existing snapshots had `days_to_earnings` but often lacked `next_earnings_date`; deriving the date from the snapshot as-of business-day offset should repair replay coverage without touching strategy logic.

## Historical Check

- `exp-20260508-004`: candidate/signal touch fields were repaired, but `rows_with_next_earnings_date = 0` and `estimate_revision_usable_rows = 0`.
- `exp-20260507-900`: forward estimate-revision ledger existed but had no usable rows.
- `exp-20260508-002`: filing-shock audit remained blocked by directional field availability; this repair only targets the earnings event key.

## What Changed

`quant/earnings_snapshot.py` now derives `next_earnings_date` when all of the following are true:

- `next_earnings_date` is missing.
- `days_to_earnings` is present in the PIT snapshot input.
- The date can be reconstructed by adding weekday business days from the snapshot as-of date.

Derived rows are marked with `next_earnings_date_source = derived_from_days_to_earnings` and `next_earnings_date_inferred = true`.

## Coverage Result

| Metric | Before exp-20260508-004 | After repair copy |
| --- | ---: | ---: |
| rows | 48 | 48 |
| rows with next earnings date | 0 | 41 |
| rows with prior same event | 0 | 39 |
| usable estimate-revision rows | 0 | 39 |
| matched candidate rows | 2 | 2 |
| usable + matched candidate rows | 0 | 1 |
| matched selected signal rows | 0 | 0 |

Matched candidate tickers: `GS, LITE`.

## PIT Status

The repaired experiment snapshots preserve the original source snapshot mtimes:

- `20260504` source mtime: 2026-05-05 UTC
- `20260505` source mtime: 2026-05-06 UTC
- `20260506` source mtime: 2026-05-07 UTC

The repaired field is derived from already-persisted PIT `days_to_earnings`, not from future price or period-end data. Still, this is a same-event key repair, not alpha evidence by itself.

## Caveats

- DTE-derived dates are stable event keys, not independent vendor-confirmed announcement timestamps.
- DTE=0 rows can include event-day estimate/actual contamination and need separate labeling before forward-return alpha evidence.
- Global `data/earnings_snapshot_*.json` files were not rewritten in this experiment; only repaired copies under `data/experiments/exp-20260508-006` were generated.

## Decision

`data_gap_repaired`: same-event ledger coverage is repaired. Keep downstream filing/earnings alpha in shadow-only mode until event-day contamination and forward returns are audited.

## Next Minimal Action

Build the estimate-revision shadow audit over usable rows, but exclude or separately bucket DTE=0/event-day rows first. Then compute forward 5/10/20/60d returns and candidate slot conflict value for matched candidates.
