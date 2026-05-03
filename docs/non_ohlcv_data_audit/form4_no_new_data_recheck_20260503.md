# Form 4 Insider Overlay No-New-Data Recheck

- experiment_id: `exp-20260503-026`
- timestamp: `2026-05-03T11:04:47+00:00`
- decision: `data_gap`
- production_impact: `data_audit_only`

## Hypothesis

Open-market insider Form 4 buying may confirm existing `trend_long` / `breakout_long` candidates, especially CEO/CFO purchases, cluster buying, first-time buys, and post-drawdown buys. This run only checks whether new PIT-safe transaction-level Form 4 data appeared after `exp-20260503-025`.

## Historical Check

- Exact prior audits: `exp-20260503-017`, `exp-20260503-020`, `exp-20260503-025`.
- Prior result: CIK mapping was usable, but there were 0 PIT-safe transaction-level Form 4 rows, 0 meaningful insider-buy candidates, and no measurable slot value.
- Mechanism insight: Insider/Form 4 remains a valid non-OHLCV event-confirmation family, but only after point-in-time transaction archives exist.
- This is not a simple rerun: no zero-row shadow replay was executed; the run only checked whether new local evidence exists.

## Current Data Availability

- New relevant local inputs after `exp-20260503-025`: 0.
- New Form 4 / insider-specific local inputs after `exp-20260503-025`: 0.
- Archived news Form 4 items: 0.
- SEC source diagnostics available: 1 file; current SEC feeds are `8-K`, `10-Q`, and `10-K`, not Form 4 owner transactions.
- Submission-cache Form 4 metadata rows: 34,738; current-universe rows: 72.
- PIT status: not safe. Submission cache is latest-snapshot metadata and lacks transaction XML fields.

## CIK Mapping Gap Report

- Core mapped: 43/45; missing: `IWM`, `SNXX`.
- Pilot mapped: 3/3; missing: none.
- Observation mapped: 13/13; missing: none.
- Interpretation: CIK mapping is not the binding blocker; missing transaction-level Form 4 data is.

## Required Field Availability

- Available: `ticker`, `cik`, `accession_number`, `filing_datetime`.
- Missing: `transaction_date`, `officer_title`, `is_director`, `is_officer`, `is_10pct_owner`, `transaction_code`, `shares`, `price`, `transaction_value`, `direct_or_indirect`, `ownership_nature`, `10b5_1_flag`, `option_exercise_flag`, `open_market_purchase_flag`, `usable_trade_date`, `pit_safe_flag`.

## Shadow Metrics

- meaningful insider-buy candidate_count: 0.
- signals_with_meaningful_insider_buy: 0.
- insider_buy_but_no_signal: 0.
- candidate overlap and slot value: not measurable because there are no PIT-safe tagged candidates.
- forward 5/10/20/60/90d returns: count 0 for all horizons.
- expected_value_score_delta: 0.0.

## Decision

`data_gap`. Do not promote Form 4 overlay, do not infer alpha from static Form 4 metadata, and do not rerun this same shadow test until transaction-level PIT rows exist.

## Next Minimum Action

Build a default-off append-only Form 4 adapter for SEC `owner=include&type=4` feeds and transaction XML parsing. Rerun shadow tagging only after nonzero PIT-safe open-market purchase rows accumulate.
