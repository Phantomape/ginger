# SEC Filing Shadow Event Schema

This schema is a shadow research contract only. It is not connected to `quant/signal_engine.py`, `quant/risk_engine.py`, `quant/portfolio_engine.py`, or the daily order path.

## Required Row Fields

| Field | Type | PIT rule | Current source |
|---|---|---|---|
| `ticker` | string/null | Must come from the CIK-to-ticker map used by the dated snapshot. | `data/sec_company_tickers.json` through `quant/sec_ticker_map.py` |
| `event_date` | YYYY-MM-DD/null | Accepted date, not fiscal/report period end. | `accepted_at` date in `sec_filing_events_YYYYMMDD.jsonl` |
| `usable_trade_date` | YYYY-MM-DD/null | First EOD date after the accepted timestamp is tradable; never use `period_end_date` / `report_date` as entry date. | `usable_trade_date` in `sec_filing_events_YYYYMMDD.jsonl` |
| `form_type` | string/null | SEC form in the source feed. | `8-K`, `10-Q`, `10-K` metadata from SEC submissions |
| `accepted_datetime` | ISO datetime/null | Required before any replay use. | `accepted_at` |
| `fiscal_period_end` | YYYY-MM-DD/null | Optional context only; cannot determine entry timing. | `report_date` when present |
| `eps_surprise` | number/null | Must be from a PIT earnings snapshot or vendor archive. | Missing for SEC rows |
| `revenue_surprise` | number/null | Must be from PIT XBRL/vendor data. | Missing |
| `gross_margin_delta` | number/null | Must be from PIT XBRL/companyfacts with period alignment. | Missing |
| `fcf_to_net_income_gap` | number/null | Must be from PIT XBRL/companyfacts with period alignment. | Missing |
| `inventory_growth` | number/null | Must be from PIT XBRL/companyfacts with period alignment. | Missing |
| `receivables_growth` | number/null | Must be from PIT XBRL/companyfacts with period alignment. | Missing |
| `guidance_raise_cut` | `raise`/`cut`/null | May come from LLM/news or explicit filing text, logged with source. | Headline/summary regex only in this audit |
| `eight_k_item_type` | list | Item labels from the SEC filing metadata or filing text packet. | `eight_k_item_codes` |
| `accession_number` | string/null | Stable event key for joining filing metadata, text, XBRL, and paper ledgers. | SEC submissions |
| `reaction_bucket` | string/null | Shadow-only event-sleeve classifier; not a production rule unless explicitly promoted elsewhere. | Default-off SEC event queue outputs |
| `paper_status` | string/null | `pending_next_session_open`, `open`, `closed`, or null. | Default-off SEC paper state files |
| `data_source` | string | Concrete dated archive path used for the row. | `data/non_ohlcv/sec_filing_events_YYYYMMDD.jsonl` |
| `pit_safe` | bool | True only when source timestamp and accession/url exist; backfilled SEC public timestamps are PIT proxies, not proof local production observed the filing. | `pit_safe_flag` plus source caveat |

## Adapter TODO

1. Persist SEC raw rows daily with CIK, ticker, accession, form, accepted datetime, URL, report date, and 8-K item labels.
2. Add same-accession point-in-time XBRL extraction for revenue, gross margin, FCF, net income, inventory, receivables, and fiscal-period alignment.
3. Join PIT earnings snapshots for EPS estimate and historical surprise only when the snapshot date is <= usable trade date.
4. Persist structured filing-text / LLM event grades separately from hard risk rules, then join by accession.
5. Keep this table shadow-only until a default-off replay freezes same-day core alternatives before entry and accumulates closed forward outcomes.
