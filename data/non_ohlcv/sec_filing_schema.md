# SEC Filing Shadow Event Schema

This schema is a shadow research contract only. It is not connected to `quant/signal_engine.py`, `quant/risk_engine.py`, `quant/portfolio_engine.py`, or the daily order path.

## Required Row Fields

| Field | Type | PIT rule | Current source |
|---|---|---|---|
| `ticker` | string/null | Must come from CIK-to-ticker mapping available as of the archive date. | `data/sec_company_tickers.json` via archived SEC item enrichment |
| `event_date` | YYYY-MM-DD/null | Accepted/published date, not fiscal period end. | `published_at` date |
| `usable_trade_date` | YYYY-MM-DD/null | First EOD date after the accepted timestamp is tradable; never use `period_end_date`. | Shadow calendar approximation only |
| `form_type` | string/null | SEC form in the source feed. | `8-K`, `10-Q`, `10-K` Atom feed metadata |
| `accepted_datetime` | ISO datetime/null | Required before any replay use. | `published_at` |
| `fiscal_period_end` | YYYY-MM-DD/null | Optional context only; cannot determine entry timing. | Missing in current archive rows |
| `eps_surprise` | number/null | Must be from a PIT earnings snapshot or vendor archive. | Missing for SEC rows |
| `revenue_surprise` | number/null | Must be from PIT XBRL/vendor data. | Missing |
| `gross_margin_delta` | number/null | Must be from PIT XBRL/companyfacts with period alignment. | Missing |
| `fcf_to_net_income_gap` | number/null | Must be from PIT XBRL/companyfacts with period alignment. | Missing |
| `inventory_growth` | number/null | Must be from PIT XBRL/companyfacts with period alignment. | Missing |
| `receivables_growth` | number/null | Must be from PIT XBRL/companyfacts with period alignment. | Missing |
| `guidance_raise_cut` | `raise`/`cut`/null | May come from LLM/news or explicit filing text, logged with source. | Headline/summary regex only in this audit |
| `eight_k_item_type` | list | Item labels from the archived 8-K summary. | SEC Atom summary |
| `data_source` | string | Concrete archive path used for the row. | `data/news_20260502.json` |
| `pit_safe` | bool | True only when source timestamp and URL exist; full replay still needs archive depth. | Computed |

## Adapter TODO

1. Persist SEC raw rows daily with CIK, ticker, form, accepted datetime, URL, and 8-K item labels.
2. Add point-in-time XBRL/companyfacts extraction for fiscal period end, revenue, gross margin, FCF, net income, inventory, and receivables.
3. Join PIT earnings snapshots for EPS estimate and historical surprise only when the snapshot date is <= usable trade date.
4. Keep this table shadow-only until a default-off replay freezes same-day core alternatives before entry.
