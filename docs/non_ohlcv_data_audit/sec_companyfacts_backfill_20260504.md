# SEC Companyfacts backfill

- Run date: `2026-05-04`
- Window: `2024-10-02 -> 2026-04-21`
- Output: `data/non_ohlcv/sec_companyfacts_selected_20241002_20260421.jsonl`
- Summary: `data/non_ohlcv/sec_companyfacts_backfill_summary_20241002_20260421.json`

## Coverage

- Tickers requested: `52`
- Tickers with CIK: `51`
- Missing CIK: `SNXX`
- Rows written: `17,109`
- Error count: `0`
- Companyfacts cache: `data/sec_companyfacts_cache`

## Fields

Selected canonical fields:

`assets`, `capex`, `cost_of_revenue`, `eps_basic`, `eps_diluted`, `equity`,
`gross_profit`, `inventory`, `liabilities`, `net_income`,
`operating_cash_flow`, `operating_income`, `receivables`, `revenue`,
`shares_diluted`.

Top row counts:

| Field | Rows |
|---|---:|
| equity | 2,064 |
| net_income | 2,035 |
| revenue | 1,480 |
| eps_basic | 1,380 |
| eps_diluted | 1,380 |
| shares_diluted | 1,316 |
| operating_income | 1,179 |
| operating_cash_flow | 1,024 |

## Caveat

SEC Companyfacts `filed` date is a public-availability PIT proxy. It is suitable
for historical replay after filing availability, but it does not prove the local
production pipeline observed these facts on that date.
