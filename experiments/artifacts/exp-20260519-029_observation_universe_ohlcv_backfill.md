# exp-20260519-029 Observation-Universe OHLCV Backfill

## Summary

- Status: `completed_with_explicit_zero_rows`
- Network enabled: `True`
- Target tickers: `86`
- Added from cache: `33` window-ticker slots
- Added from Yahoo: `87` window-ticker slots
- Provider/network failures: `0`
- Explicit zero-row slots: `3`
- Post-window zero-row slots: `3`

## Window Outputs

| Window | Output snapshot | Output tickers | With rows | Full | Partial | Zero rows | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | `data\experiments\exp-20260519-029\ohlcv\exp-20260519-029_late_strong_current_universe_ohlcv.json` | 94 | 85 | 83 | 2 | 1 | 0 |
| mid_weak | `data\experiments\exp-20260519-029\ohlcv\exp-20260519-029_mid_weak_current_universe_ohlcv.json` | 93 | 85 | 83 | 2 | 1 | 0 |
| old_thin | `data\experiments\exp-20260519-029\ohlcv\exp-20260519-029_old_thin_current_universe_ohlcv.json` | 93 | 85 | 81 | 4 | 1 | 0 |

## Production Impact

- No shared policy change.
- No backtester or production adapter change.
- Canonical OHLCV snapshots under `data/ohlcv` were not modified.
- These snapshots are replay inputs for future core-expansion experiments only.
