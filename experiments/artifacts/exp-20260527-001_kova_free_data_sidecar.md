# exp-20260527-001 Kova Free Data Sidecar

## Decision

`accepted_default_off_kova_free_data_sidecar`. This is measurement repair only: no strategy, ranking, sizing, exit, LLM/news, universe, or order path consumes the fields.

## What Was Added

- `quant/kova_data_sidecar.py`: Alpha Vantage intraday parser/fetcher, SEC Companyfacts growth derivation, SEC 13F zip parser, Ginger RS proxy, and as-of loader.
- `scripts/run_kova_data_refresh.py`: forward/backfill refresh entry point.
- `quant/test_kova_data_sidecar.py`: PIT and parser tests.

## Sample Run

`2026-04-21` sample for `AAPL/MSFT/NVDA`: fundamentals rows `728`, RS rows `3`, intraday skipped rows `3`, 13F skipped rows `3`.

Intraday needs `ALPHA_VANTAGE_API_KEY`; 13F needs a supplied/downloaded SEC 13F zip and CUSIP map for ticker joins.

## Verification

- `pytest quant\test_kova_data_sidecar.py`: 6 passed.
- `py_compile quant\kova_data_sidecar.py scripts\run_kova_data_refresh.py`: passed.

## Next Use

Future experiments may join these rows with `ticker` and `asof_date <= signal_date`. Any use as a VCP gate, stop/R policy, or pyramid/add-on rule needs a separate Gate 1-4 replay.
