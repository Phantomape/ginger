# Form 4 Insider Overlay No-New-Data Recheck

- experiment_id: `exp-20260503-033`
- timestamp: `2026-05-03T14:07:34+00:00`
- source: `SEC Form 4 insider ownership filings`
- mechanism_family: `non_ohlcv_event_confirmation_insider_form4`
- decision: `data_gap`
- production_impact: `data_audit_only`

## Hypothesis

Open-market insider Form 4 buying may confirm existing trend_long/breakout_long candidates, but prior same-day Form 4 audits already found no PIT-safe transaction-level data; this run only checks whether new local Form 4 evidence exists after exp-20260503-030.

## Historical Check

- Exact prior Form 4 audits: `exp-20260503-017`, `exp-20260503-020`, `exp-20260503-025`, `exp-20260503-026`, `exp-20260503-030`.
- Prior result: CIK mapping was usable, but PIT-safe transaction-level Form 4 rows were unavailable.
- This recheck found `0` new relevant local Form 4 inputs after `exp-20260503-030`.

## Coverage And PIT Status

- CIK mapping: core 43/45, pilot 3/3, observation 13/13.
- Missing core CIKs: ['IWM', 'SNXX'].
- Archived news Form 4 items: 0 across 0 files.
- SEC source diagnostics feed types: ['10-K', '10-Q', '8-K'].
- Submission cache Form 4 metadata rows: 34738; current-universe rows: 72.
- PIT-safe transaction-level rows: `0`.
- Submission cache status: biased latest snapshot, useful for schema discovery only.

## Required Field Availability

- Available: ticker, cik, accession_number, filing_datetime.
- Missing: transaction_date, officer_title, is_director, is_officer, is_10pct_owner, transaction_code, shares, price, transaction_value, direct_or_indirect, ownership_nature, 10b5_1_flag, option_exercise_flag, open_market_purchase_flag, usable_trade_date, pit_safe_flag.

## Shadow Metrics

- candidate_count: `0` meaningful insider-buy candidates.
- overlap_with_existing_signals: `0`; no PIT-safe rows to join.
- scarce-slot opportunity cost: not measurable.
- forward 5/10/20/60/90d returns: not measurable because tagged candidate count is `0`.

## Next Minimum Action

Build a default-off append-only Form 4 adapter for SEC owner=include type=4 feeds and transaction XML parsing; rerun shadow tagging only after nonzero PIT-safe open-market purchase rows accumulate.
