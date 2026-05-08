# Estimate Revision Forward Ledger Harness (exp-20260507-900)

## Decision

`shadow_only`: the forward ledger harness is accepted, but no alpha is accepted. Production signal, ranking, sizing, exits, and portfolio logic are unchanged.

## Hypothesis

A forward-only estimate revision ledger with same-event identity and PIT flags can unblock later analyst-revision alpha tests for existing `trend_long` and `breakout_long` candidates.

## Mechanism Family

`analyst_estimate_revision_earnings_quality_overlay`

## Single Causal Variable

`forward estimate revision ledger schema and PIT-safe same-event delta construction only`

## What Changed

- `quant/earnings_snapshot.py` now persists `next_earnings_date`, which `get_earnings_data()` already produced, and reports `tickers_with_next_earnings_date` coverage.
- `quant/estimate_revision_ledger.py` builds same-event EPS estimate delta rows and marks whether each row is PIT-usable.
- `scripts/run_estimate_revision_forward_ledger.py` writes default-off ledger and summary artifacts.
- `quant/run.py` now calls the same ledger helper after the daily earnings snapshot, so the daily operator flow remains one command: `python quant/run.py`.
- `quant/report_generator.py` surfaces the ledger row/usable/up/down counts inside the existing non-OHLCV coverage block.
- `quant/test_estimate_revision_ledger.py` covers snapshot schema persistence, same-event delta logic, event-roll rejection, and backfill PIT rejection.

## Smoke Output

Command:

```bash
python scripts/run_estimate_revision_forward_ledger.py --as-of 2026-05-06 --output-dir data/experiments/exp-20260507-900 --start 2026-05-04
```

Summary:

- Ledger rows: 48
- Tickers with EPS estimate: 41
- Rows with next earnings date: 0
- Rows with prior same-event snapshot: 0
- PIT-usable revision rows: 0
- Up revisions: 0
- Down revisions: 0
- Same-day feature row matches: 48
- Same-day candidate matches: 2 (`GS`, `LITE`)
- Same-day selected signal matches: 0

The zero usable rows are expected because the existing `2026-05-06` snapshot was written before `next_earnings_date` was persisted. The harness becomes useful after at least two forward snapshots with the new schema exist.

## PIT Rule

A row is usable only if:

- current snapshot has `next_earnings_date` and `eps_estimate`;
- prior snapshot for the same ticker has the same `next_earnings_date`;
- current and prior snapshot files were created no later than one UTC calendar day after their respective `as_of_date`;
- EPS estimate delta is computed within that same event identity.

## Production Impact

No trading behavior changed. This is a data schema and default-off artifact generator only. The run adapter now writes the observation artifact during the normal daily `run.py` flow, but it does not alter signals, ranking, sizing, exits, orders, or portfolio heat.

## Verification

- `pytest quant/test_estimate_revision_ledger.py -q` -> 7 passed
- `pytest quant/test_quant.py -k persist_earnings_snapshot -q` -> 3 passed, 300 deselected
- `pytest quant/test_daily_non_ohlcv_snapshot.py -q` -> 3 passed

## Next Minimum Action

Run the ledger after the next two daily earnings snapshots. Once 30-60 forward trading days of PIT-usable revision rows exist, evaluate whether positive revision tags improve existing A/B candidate forward returns and scarce-slot value.
