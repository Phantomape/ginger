# exp-20260519-030 Broad-Market OHLCV Warehouse v1

## Summary

- Status: `warehouse_built_with_provider_gaps`
- SQLite warehouse: `data\experiments\exp-20260519-030\warehouse_main.sqlite`
- SEC reference tickers: `10341`
- Hygiene-pass tickers: `7483`
- OHLCV rows stored: `4964023`
- Tickers with OHLCV rows: `8499`
- Hygiene-pass tickers with OHLCV rows: `7263`
- Remaining hygiene tickers without rows: `220`
- Pending hygiene tickers not yet attempted: `0`
- Hygiene no-row provider gaps: `220`
- Hygiene rate-limited tickers: `0`
- Fetch status counts: `{"downloaded": 8412, "no_rows": 311, "seeded_local": 87}`
- Download requested in latest run: `0`

## Coverage

```json
{
  "coverage_status_counts": {
    "all_windows_full_liquid": 1446,
    "any_window_full_liquid": 431,
    "not_research_ready": 5386
  },
  "full_liquid_window_distribution": {
    "0": 5386,
    "1": 241,
    "2": 190,
    "3": 1446
  }
}
```

## Notes

- This is a replay data warehouse, not a core-universe promotion.
- Canonical snapshots and live production policy are unchanged.
- Resume future runs with the same script and SQLite path.
