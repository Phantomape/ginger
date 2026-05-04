# Form 4 Transaction Backfill

- generated_at: `2026-05-03`
- window: `2024-10-02` to `2026-05-02`
- production_impact: `data_backfill_only`
- strategy_logic_changed: `false`

## Output

- transaction rows: `data/non_ohlcv/form4_transactions_20241002_20260502.jsonl`
- summary: `data/non_ohlcv/form4_backfill_summary_20241002_20260502.json`
- raw XML cache: `data/sec_form4_xml_cache`
- parser: `quant/form4_backfill.py`

## Result

- tickers requested: 52
- tickers mapped to SEC CIK: 51
- missing CIK tickers: `SNXX`
- Form 4 filings seen: 6,558
- primary documents fetched/read: 6,558
- transaction rows written: 27,879
- PIT-safe rows: 27,879
- parser errors: 0
- external issuer rows excluded: 1,171
- code `P` open-market purchase rows: 131
- option exercise rows: 7,516
- rows with 10b5-1 text evidence: 12,332

## Notes

The SEC submissions `primaryDocument` path commonly points to `xslF345X05/...xml`,
which returns an HTML rendering page. The backfill parser therefore resolves the raw
XML by dropping the `xslF345X05/` rendering prefix and caches the raw document.

The parser uses the XML `issuerTradingSymbol` and `issuerCik` as the traded
issuer, not the SEC submission CIK. This matters because company submission
history can include cases where the requested CIK is a reporting owner rather
than the issuer being traded. By default, rows where the XML issuer ticker is
outside the requested universe are excluded.

`open_market_purchase_flag` is a mechanical Form 4 transaction tag:
`transaction_code == P` and `acquired_disposed_code == A`. It is not yet a
tradeable alpha signal. Before using it for ranking or entry confirmation, add a
shadow-only overlay that excludes issuer/self rows, tiny purchases, option-related
noise, 10b5-1 planned trades when appropriate, and measures forward returns by
usable trade date.

## Verification

`python -m pytest quant/test_form4_backfill.py quant/test_sec_submissions.py`
passed with 8 tests.
