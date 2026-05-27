# exp-20260527-014 Kova Sidecar Production Wiring

## Decision

Accepted as `measurement_repair`: the Kova free-data sidecar now runs inside
the daily production pipeline as default-off context accumulation. It writes
read-only snapshots and does not alter entries, ranking, sizing, exits,
LLM/news, universe, or orders.

## What Changed

- `quant/run.py` imports `persist_kova_data_snapshot`.
- The daily run passes the already-loaded production OHLCV dictionary plus
  `SPY` into the sidecar, avoiding a second OHLCV fetch.
- The sidecar summary is attached to `non_ohlcv_snapshot["kova_data_sidecar"]`.
- Heavy external surfaces stay explicit env-gated:
  `KOVA_REFRESH_INTRADAY`, `ALPHA_VANTAGE_API_KEY`,
  `KOVA_REFRESH_COMPANYFACTS`, `KOVA_COMPANYFACTS_LOOKBACK_DAYS`,
  `KOVA_SEC13F_ZIP`,
  `KOVA_SEC13F_YEAR`, `KOVA_SEC13F_QUARTER`, `KOVA_CUSIP_MAP`, and
  `KOVA_REFRESH_SEC13F`.
- `quant/kova_data_sidecar.py` now accepts in-memory OHLCV mappings, including
  pandas DataFrames, and preserves multi-row context surfaces for later
  as-of joins.

## Efficiency Notes

The default production path is cheap:

- RS proxy uses in-memory OHLCV from the current run.
- Companyfacts growth uses local selected Companyfacts rows, skips file ranges
  outside the filed-date window, and dedupes overlapping files. The default
  production lookback is `820` days, enough for YoY joins without sweeping the
  whole archive each day.
- Intraday Alpha Vantage calls are skipped unless explicitly enabled.
- SEC 13F ingestion is skipped unless a zip/year-quarter is explicitly
  supplied.
- Missing optional data writes `skipped` rows rather than failing the run.

## Gates

Gate 1: passed. Baseline is `exp-20260527-001`, which created the default-off
Kova sidecar.

Gate 2: passed. Required production inputs are the existing OHLCV dict, optional
`SPY`, local non-OHLCV Companyfacts rows, and optional env-gated external
sources.

Gate 3: passed. No filter is added and no candidate pool changes.

Gate 4: passed for measurement repair only. Strategy metrics are unchanged by
construction because no strategy path consumes the fields.

## Verification

- `.\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_kova_data_sidecar.py`
- `.\\.venv\\Scripts\\python.exe -B -m py_compile quant\\run.py quant\\kova_data_sidecar.py scripts\\run_kova_data_refresh.py`

The full production command was not run during closeout because it can invoke
live data/news/LLM paths. This experiment only verifies the production sidecar
call path and the sidecar writer contract.

## Follow-Up Boundary

Any future use of these Kova fields in VCP gates, ranking, sizing, exits, or
orders requires a new `alpha_search` ticket and full Gate 1-4 replay.
