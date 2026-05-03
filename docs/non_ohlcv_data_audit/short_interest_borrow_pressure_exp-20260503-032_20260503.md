# Short Interest / Borrow Pressure Data Audit - exp-20260503-032

Date: 2026-05-03
Mode: data audit / duplicate guardrail / shadow blocked
Mechanism family: short_interest_borrow_pressure_overlay
Single causal variable: new PIT-safe short-interest or borrow-pressure evidence since exp-20260503-028

## Hypothesis

High short interest alone is not a long signal. High short crowding plus existing breakout/trend strength or positive event context may mark squeeze-ready candidates; high short crowding plus negative filing/news/earnings context may mark fragile candidates. This run only checks whether new point-in-time evidence exists after exp-20260503-028.

## Historical Check

Same-family records found:

- exp-20260503-015: initial short/borrow coverage audit, data_gap.
- exp-20260503-018: duplicate guardrail, no new PIT rows.
- exp-20260503-021: recheck, no new PIT rows.
- exp-20260503-023: recheck, no new PIT rows; data/non_ohlcv contained SEC artifacts only.
- exp-20260503-028: latest exact recheck, still 0 structured short-interest rows, 0 FINRA adapter/files, 0 paid borrow rows, and 0 PIT-safe rows.

Mechanism insight from docs/alpha-optimization-playbook.md: short interest / borrow pressure is a plausible non-OHLCV overlay, but only as shadow-quality until PIT data exists. FINRA daily short volume must not be treated as short interest.

## Availability Result

| Source / field | Status |
| --- | --- |
| structured short-interest files | 0 |
| structured short-interest rows | 0 |
| FINRA adapter files | 0 |
| FINRA daily short-volume files | 0 |
| paid borrow files | 0 |
| borrow_fee rows | 0 |
| shares_available rows | 0 |
| hard_to_borrow rows | 0 |
| usable_trade_date rows | 0 |
| PIT-safe rows | 0 |
| new short/borrow files since exp-20260503-028 | 0 |
| unstructured short-interest/news headline matches | 52; not treated as structured PIT evidence |

## PIT Risk

Short-interest settlement dates are not tradable without publication dates and a usable_trade_date. FINRA daily short volume is trading activity, not short positioning. MarketBeat, Stocktwits, and generic news headline mentions do not provide a reproducible short-interest, float, borrow-fee, or shares-available time series. Without borrow_fee or shares_available, squeeze confidence must be downgraded.

## Shadow Status

Shadow tagging was not run because there are 0 PIT-safe rows. Planned but blocked fields:

- short_crowding_score
- short_change_score
- squeeze_setup_score
- fragile_short_score

Candidate overlap and slot value are not measurable: 0 taggable candidates, 0 tagged existing signals, no forward 5/10/20/60d return sample.

## Decision

Decision: data_gap.
Production impact: data_audit_only; no production, backtester, run, signal, risk, portfolio, universe, ranking, or LLM prompt change.

## Next Minimal Action

Build a default-off append-only short/borrow data contract only after a real source is selected. Required fields remain: ticker, settlement_date, publication_date, short_interest, short_interest_float, days_to_cover, short_interest_change, borrow_fee, shares_available, hard_to_borrow, daily_short_volume, total_volume, daily_short_volume_ratio, usable_trade_date, and pit_safe. Rerun shadow tagging only after nonzero PIT rows exist.
