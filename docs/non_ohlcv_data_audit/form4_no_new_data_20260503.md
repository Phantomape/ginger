# Form 4 Insider Overlay No-New-Data Recheck

- experiment_id: `exp-20260503-025`
- timestamp: `2026-05-03T10:07:57+00:00`
- decision: `data_gap`
- production_impact: `data_audit_only`

## Hypothesis

Open-market insider Form 4 buying may confirm existing trend_long/breakout_long candidates, but prior Form 4 audits already found no PIT-safe transaction-level data; this run only rechecks whether new local Form 4 evidence exists before any shadow rerun.

## Historical Check

- Exact prior audit: `exp-20260503-017`.
- Prior duplicate guardrail: `exp-20260503-020`.
- Prior result: CIK mapping was usable, but there were 0 PIT-safe transaction-level Form 4 rows and 0 meaningful insider-buy candidates.
- Mechanism insight: Insider/Form 4 remains a valid non-OHLCV family, but only after point-in-time transaction archives exist.

## Current Data Availability

- New relevant local inputs after `exp-20260503-020`: 0.
- New Form 4/insider-specific inputs after `exp-20260503-020`: 0.
- Archived news Form 4 items: 0 across 0 files.
- SEC source diagnostics available: 1 file(s); current SEC feeds are 8-K / 10-Q / 10-K, not Form 4 owner transactions.
- Submission-cache Form 4 metadata rows: 34738; current-universe rows: 72.
- PIT status: not safe. Submission cache is a latest snapshot and lacks transaction XML fields.

## CIK Mapping Gap Report

- Core mapped: 43/45; missing: ['IWM', 'SNXX'].
- Pilot mapped: 3/3; missing: [].
- Observation mapped: 13/13; missing: [].
- Interpretation: CIK mapping is not the binding blocker; missing transaction-level Form 4 data is.

## Required Field Availability

- Available: ticker, cik, accession_number, filing_datetime.
- Missing: transaction_date, officer_title, is_director, is_officer, is_10pct_owner, transaction_code, shares, price, transaction_value, direct_or_indirect, ownership_nature, 10b5_1_flag, option_exercise_flag, open_market_purchase_flag, usable_trade_date, pit_safe_flag.

## Shadow Metrics

- meaningful insider-buy candidate_count: 0
- signals_with_meaningful_insider_buy: 0
- insider_buy_but_no_signal: 0
- candidate overlap and slot value: not measurable because there are no PIT-safe tagged candidates.
- forward 5/10/20/60/90d returns: count 0 for all horizons.

## Next Minimum Action

Build a default-off append-only Form 4 adapter for SEC owner=include type=4 feeds and transaction XML parsing; rerun shadow tagging only after nonzero PIT-safe open-market purchase rows accumulate.
