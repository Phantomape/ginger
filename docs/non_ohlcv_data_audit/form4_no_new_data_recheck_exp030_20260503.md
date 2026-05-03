# Form 4 Insider Overlay Recheck

- experiment_id: `exp-20260503-030`
- run_time: `2026-05-03T12:04:27+00:00`
- source: SEC Form 4 insider ownership filings
- mechanism_family: `non_ohlcv_event_confirmation_insider_form4`
- mode: data audit only; no production change

## Hypothesis

Open-market insider buying, especially CEO/CFO large buys, cluster buying,
first purchases, and post-drawdown buys, may confirm existing
`trend_long` / `breakout_long` candidates. This run does not create standalone
entries and does not touch the production signal path.

## Historical Check

Direct prior Form 4 audits already exist:

- `exp-20260503-017`: first Form 4 availability audit; decision `data_gap`.
- `exp-20260503-020`: duplicate guardrail recheck; no new PIT-safe data.
- `exp-20260503-025`: no-new-data recheck; no transaction-level rows.
- `exp-20260503-026`: same-family recheck; no new local Form 4 inputs.

The playbook ranks Insider/Form 4 as a valid external event-confirmation
source, but only as shadow/default-off evidence until transaction-level,
point-in-time archives exist.

## Current Data Availability

- New relevant local Form 4 inputs after `exp-20260503-026`: 0.
- Daily Form 4 archive: missing.
- Transaction XML archive: missing.
- Current SEC source diagnostics: only `8-K`, `10-Q`, and `10-K`; no
  `owner=include&type=4` Form 4 feed.
- Static SEC submissions cache: contains Form 4 metadata, but it is latest
  snapshot data and is biased for historical overlay performance.

CIK mapping is not the current blocker:

- core mapping: `43/45`; missing `IWM`, `SNXX`
- pilot mapping: `3/3`
- observation mapping: `13/13`

## Required Field Status

Available only as metadata:

- `ticker`
- `cik`
- `accession_number`
- `filing_datetime`

Missing transaction fields:

- `transaction_date`
- `officer_title`
- `is_director`
- `is_officer`
- `is_10pct_owner`
- `transaction_code`
- `shares`
- `price`
- `transaction_value`
- `direct_or_indirect`
- `ownership_nature`
- `10b5_1_flag`
- `option_exercise_flag`
- `open_market_purchase_flag`
- `usable_trade_date`
- `pit_safe_flag`

## Shadow Metrics

- meaningful insider-buy candidates: 0
- signals with meaningful insider buy: 0
- signals without meaningful insider buy: 0
- insider buy but no signal: 0
- overlap with existing signals: 0
- scarce-slot opportunity cost: not measurable
- forward 5/10/20/60/90d return of tagged candidates: not measurable
- expected_value_score delta: `0.0`

## Decision

Decision: `data_gap`.

Do not rerun a shadow overlay or default-off replay until nonzero PIT-safe
open-market purchase rows exist. The next minimum action is a default-off,
append-only Form 4 adapter that archives SEC `owner=include&type=4` feeds and
parses transaction XML into the required schema.
