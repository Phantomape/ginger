# exp-20260508-004 Estimate Revision Candidate Match Audit

## Hypothesis

Forward PIT earnings estimate ledgers are only useful for filing-shock shadow alpha if each row declares whether it touched same-day Ginger feature rows, candidate objects, or selected signals. This is a default-off audit harness only.

## Historical Check

- `exp-20260507-900`: forward estimate revision ledger existed, but 2026-05-06 had 0 `next_earnings_date`, 0 prior same-event rows, and 0 usable revision rows.
- `exp-20260507-093`: SEC same-accession facts did not touch historical A/B candidates.
- `exp-20260508-002`: fresh SEC/earnings filing-shock coverage remained a data gap because numeric directional fields were unavailable.

## Data Source And PIT

- Earnings source: `data/earnings_snapshot_20260506.json`.
- Signal touch sources: `data/quant_signals_20260506.json`, `data/trend_signals_20260506.json`.
- PIT status: snapshot file mtime passes the current PIT heuristic, but all 48 rows are blocked by missing `next_earnings_date`, so estimate-revision evidence is not tradable shadow alpha yet.

## Coverage

| Metric | Value |
| --- | ---: |
| rows | 48 |
| tickers with EPS estimate | 41 |
| rows with next earnings date | 0 |
| usable estimate-revision rows | 0 |
| matched feature rows | 48 |
| matched candidate rows | 2 |
| matched selected signal rows | 0 |
| candidate match rate | 0.041667 |

Matched candidate tickers: `GS, LITE`.

## Interpretation

The candidate-touch schema is now repaired: the ledger can distinguish trend feature rows from real candidate objects and selected signals. On 2026-05-06, every ledger ticker had a trend feature row, but only `GS` and `LITE` matched default-off event candidate objects, and no ticker matched a selected production signal.

The alpha data gap remains: `next_earnings_date` is missing for all rows, so same-event estimate revisions cannot be identified and should not be used as production or replay evidence.

## Decision

`data_gap`: harness repaired, content gap remains. No production signal path, ranking, sizing, risk, or order logic changed.

## Next Minimal Action

Fix `next_earnings_date` coverage in earnings snapshots, then rerun this ledger on consecutive dates for the same upcoming earnings event. Only after usable rows overlap candidates should we compute forward 5/10/20/60d returns or slot conflict value.
