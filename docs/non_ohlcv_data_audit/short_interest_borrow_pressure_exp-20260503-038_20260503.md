# Short Interest / Borrow Pressure Data Audit

Experiment: `exp-20260503-038`  
Timestamp: `2026-05-03T15:05:30+00:00`  
Mode: data audit only / duplicate-guardrail recheck  
Production impact: none

## Hypothesis

High short crowding plus existing Ginger strength or positive event context may mark squeeze-ready candidates. High short crowding plus negative filing, news, or earnings context may mark fragile candidates. This should be an overlay for existing `breakout_long`, `trend_long`, or event-confirmed candidates, not a standalone entry.

## Historical Check

This exact mechanism has already been audited in `exp-20260503-015`, `exp-20260503-018`, `exp-20260503-021`, `exp-20260503-023`, `exp-20260503-028`, `exp-20260503-032`, and `exp-20260503-034`.

Prior result: `data_gap`. The repo had 0 structured short-interest rows, 0 FINRA adapter/files, 0 paid borrow rows, 0 PIT-safe rows, 0 usable trade-date rows, and 0 taggable candidates.

Mechanism insight remains unchanged: `docs/alpha-optimization-playbook.md` treats short interest / borrow pressure as a valid external overlay source only when PIT-safe data exists. It explicitly warns against treating FINRA daily short volume as short interest.

## Current Recheck

Scope searched:

- `data`
- `data/non_ohlcv`
- `quant`
- `scripts`
- recent `data/news_*`, `data/clean_news_*`, and `data/clean_trade_news_*` archives

Results:

| Item | Count | Status |
| --- | ---: | --- |
| Structured short-interest files | 0 | missing |
| Structured short-interest rows | 0 | missing |
| FINRA adapter files | 0 | missing |
| FINRA daily short-volume files | 0 | missing |
| Paid borrow files | 0 | missing |
| Borrow-fee rows | 0 | missing |
| Shares-available rows | 0 | missing |
| Hard-to-borrow rows | 0 | missing |
| PIT-safe rows | 0 | missing |
| Usable trade-date rows | 0 | missing |
| Name/adapter matches in `data`, `quant`, `scripts` | 0 | missing |
| News archive files searched | 92 | unstructured only |
| Unstructured headline matches | 184 across 37 files | biased / not usable |

`data/non_ohlcv` still contains only SEC filing artifacts:

- `data/non_ohlcv/sec_filing_schema.md`
- `data/non_ohlcv/sec_filing_shadow_events_20260503.json`

## PIT Status

PIT status: unavailable.

Required fields are unavailable because no structured short/borrow rows exist:

- `ticker`
- `settlement_date`
- `publication_date`
- `short_interest`
- `short_interest_float`
- `days_to_cover`
- `short_interest_change`
- `borrow_fee`
- `shares_available`
- `hard_to_borrow`
- `daily_short_volume`
- `total_volume`
- `daily_short_volume_ratio`
- `usable_trade_date`
- `pit_safe`

Important bias notes:

- Short-interest settlement dates are not tradable without publication dates.
- FINRA daily short volume is trading activity, not short positioning.
- News/headline mentions are not structured borrow-pressure evidence.
- Without `borrow_fee` or `shares_available`, squeeze confidence must be downgraded.

## Shadow Metrics

No shadow tagging was run because no PIT-safe rows exist.

| Metric | Value |
| --- | ---: |
| Candidate count | 0 |
| Tagged existing signals | 0 |
| Overlap with existing signals | 0.0 |
| 5d forward return | null |
| 10d forward return | null |
| 20d forward return | null |
| 60d forward return | null |
| Scarce-slot opportunity cost | not measurable |

Baseline accepted-stack metrics were unchanged because no production or replay behavior changed. Production EV delta is `0.0`; shadow EV delta is `null`.

## Decision

Decision: `data_gap`.

The mechanism remains conceptually plausible, but another short/borrow shadow replay would be fabricated without real PIT-safe rows. Do not connect this to production, do not create standalone squeeze entries, and do not interpret daily short-volume or headlines as short-interest positioning.

## Next Minimum Action

Select or build a real default-off append-only short/borrow data source contract with publication-date lag handling. Only rerun shadow tagging after nonzero PIT-safe rows exist for existing candidates.
