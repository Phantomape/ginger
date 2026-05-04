# SEC Filing Public PIT Backfill

- experiment_id: `exp-20260503-050`
- generated_at: `2026-05-03T20:25:08+00:00`
- window: `2024-10-02` to `2026-04-21`
- production_impact: `sec_public_pit_backfill_only`
- strategy_logic_changed: `false`

## Output

- events: `data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl`
- summary: `data/non_ohlcv/sec_filing_backfill_summary_20241002_20260421.json`
- cache: `data/sec_submissions_cache`
- script: `quant/sec_filing_backfill.py`

## Result

- tickers requested: 52
- tickers mapped to SEC CIK: 51
- missing CIK tickers: `SNXX`
- rows written: 1,286
- PIT-safe rows: 1,286
- error_count: 0
- submission chunks listed: 155
- submission chunks overlapping window: 9
- submission chunks read: 9

## Forms

- `8-K`: 969
- `8-K/A`: 20
- `10-Q`: 199
- `10-Q/A`: 5
- `10-K`: 88
- `10-K/A`: 5

## Top 8-K Item Codes

- `9.01`: 774
- `2.02`: 306
- `8.01`: 248
- `7.01`: 237
- `5.02`: 204
- `1.01`: 126
- `5.07`: 66
- `2.03`: 65
- `3.02`: 51
- `5.03`: 46

## PIT Interpretation

This is a SEC public-availability PIT proxy. It uses EDGAR `accepted_at`,
accession metadata, and archive URLs to estimate when a filing became public and
when an EOD process could conservatively trade it.

It is not a production-observed replay. It does not prove that historical
`news_YYYYMMDD` archives, source diagnostics, or LLM prompt/response logs
actually observed these filings at the time.

## Next Use

Use this table as the SEC event backbone for the next shadow experiment:
`SEC filing shock + earnings snapshot + price reaction`. Join by
`ticker` and `usable_trade_date`, then measure 1/5/10/20-day return and
SPY/QQQ excess return cohorts before proposing any strategy rule.

## Verification

`python -m pytest quant/test_sec_filing_backfill.py quant/test_sec_submissions.py`
passed with 6 tests.
