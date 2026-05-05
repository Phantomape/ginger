# SEC filing text backfill

- Date: `2026-05-04`
- Source events: `data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl`
- Output: `data/non_ohlcv/sec_filing_text_20241002_20260421.jsonl`
- Summary: `data/non_ohlcv/sec_filing_text_backfill_summary_20241002_20260421.json`
- Cache: `data/sec_filing_text_cache/`

## Coverage

- Input filings: `306` 8-K Item 2.02 events
- Rows written: `306`
- Status counts: `{"ok": 306}`
- Unique tickers: `48`
- Unique accessions: `306`
- Documents fetched: `1,224`
- Extracted text chars: `12,024,232`

## PIT Caveat

The SEC archive text is public and keyed by `accepted_at` / `usable_trade_date`,
but this backfill was fetched after the fact. It is a replayable public-PIT
proxy for research, not proof that the production pipeline observed every
document at the time.

## Use

This text layer is intended for SEC/event grading experiments and LLM packet
construction. It should not be used as a standalone production trading rule.
