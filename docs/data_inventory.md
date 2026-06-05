# Data One Pager

Last updated: 2026-06-05

This repo treats data as replay evidence. New artifacts should have one clear
home, and strategy code should read through canonical paths or
`quant/data_paths.py` compatibility resolvers instead of adding another copy.

## Canonical Map

| Surface | Canonical location | Use |
| --- | --- | --- |
| Fixed-window daily OHLCV | `data/ohlcv/ohlcv_snapshot_*.json` | Deterministic backtest input. The three standard windows are defined in `docs/backtesting.md`. Pilot/sleeve OHLCV variants in this directory are not canonical core baselines unless the command explicitly uses them. |
| Intraday OHLCV | `data/kova/intraday/intraday_ohlcv_YYYYMMDD.jsonl` | Kova/intraday archive. Do not substitute it for fixed-window backtest snapshots without a documented experiment. |
| Broad/full ticker OHLCV warehouse | `data/experiments/exp-20260519-030/warehouse_main.sqlite` | Broad-market OHLCV warehouse built by `exp-20260519-030`. It has `ticker_universe`, `ohlcv`, `fetch_status`, `coverage_summary`, and `run_manifest` tables; after the reference-asset seed it contains 4,968,741 OHLCV rows and 1,446 `all_windows_full_liquid` tickers. Use it as the broad stock OHLCV research superset and preferred input for new full-universe work. `quant/ohlcv_warehouse.py` can seed deterministic snapshot rows, `quant/run.py` accumulates production-downloaded OHLCV into it daily, and `quant/backtester.py --ohlcv-warehouse ...` can load it directly. |
| Non-OHLCV replay data | `data/non_ohlcv/` | SEC filings, filing text/features, Form 4, companyfacts, earnings/event snapshots, and coverage manifests. Check the coverage report before adding `require_non_ohlcv` rules. |
| Realized fundamentals (curated) | `data/kova/fundamentals/companyfacts_growth_YYYYMMDD.jsonl` | Daily Kova/CANSLIM sidecar SEC Companyfacts YoY growth for the ~40 curated trade-universe names. PIT-safe (`asof_date <= signal_date`). Built by `quant/kova_data_sidecar.py`. |
| Realized fundamentals (broad universe) | `data/kova/fundamentals/companyfacts_growth_broad_universe_YYYYMMDD.jsonl` | SEC Companyfacts realized YoY growth (revenue / eps_basic / eps_diluted / net_income) for the broad 1,446 `all_windows_full_liquid` warehouse universe. Built by `exp-20260605-007`. Free, official SEC XBRL, PIT-safe (filing date). See "Broad-Universe Realized Fundamentals" below for coverage. The clean, scalable alternative to yfinance `eps_estimate`, which is ~50-name-only and annual/quarterly contaminated. |
| Daily production archive | `data/daily/...` | News, signals, reports, LLM prompts/responses/decisions, earnings/event snapshots, universe state, and forward-test artifacts. Use `quant/data_paths.py` daily artifact helpers. |
| Operator-maintained live inputs | `operator_inputs/` | Manual/live inputs such as `open_positions.json` and `manual_trades.jsonl`. Gate 2 fields like `entry_date` and `target_price` are verified here, not under `data/`. |
| Backtest results | `data/backtests/backtest_results_*.json` | Standard backtest outputs. Root-level `data/backtest_results_*.json` is legacy compatibility only. |
| Experiment artifacts | `data/experiments/exp-YYYYMMDD-NNN/` | Per-experiment outputs, diagnostics, and local snapshots. Experiment-local OHLCV copies are allowed only as that experiment's evidence and should not become shared inputs. |
| Paper sleeves | `data/paper_sleeves/<sleeve>/state.json` and `snapshots.jsonl` | Default-off paper sleeve state and forward snapshots. These are attribution/observation surfaces unless promoted through Gate 1-4. |
| Durable state, ledgers, reference | `data/state/`, `data/ledgers/`, `data/reference/` | Persistent state, append-only ledgers, and static reference maps. Prefer named keys in `quant/data_paths.py` for shared artifacts. |
| Diagnostics, cache, tmp | `data/diagnostics/`, `data/cache/`, `data/tmp/` | Local or diagnostic artifacts. They are not acceptance evidence unless explicitly cited in an experiment closeout. |

## OHLCV Duplication Rules

- The fixed-window backtester snapshot source of truth is `data/ohlcv/`.
- The broad stock OHLCV research superset is
  `data/experiments/exp-20260519-030/warehouse_main.sqlite`.
- Current shared files include three standard windows plus pilot/sleeve variants:
  `ohlcv_snapshot_20241002_20250422.json`,
  `ohlcv_snapshot_20250423_20251022.json`,
  `ohlcv_snapshot_20251023_20260421.json`,
  `ohlcv_snapshot_20251023_20260421_with_pilot_refreshed.json`, and
  `ohlcv_snapshot_20251023_20260501_with_pilot.json`.
- Some legacy experiment code still names `data/ohlcv_snapshot_*.json`.
  `quant/data_paths.py::ohlcv_snapshot_path` maps those names to
  `data/ohlcv/` when the organized file exists. New code should call that
  helper or pass the organized `data/ohlcv/...` path directly.
- Experiment-local OHLCV snapshots under `data/experiments/<exp-id>/ohlcv/`
  are frozen evidence for that experiment only. Do not use them as future
  baselines unless a follow-up experiment promotes that exact artifact.
- The SQLite warehouse seeded the canonical stock snapshot rows and extends
  them to a much broader ticker set. Keep it aligned by running
  `.\.venv\Scripts\python.exe -B quant\ohlcv_warehouse.py seed-snapshots`
  after adding or changing deterministic `data/ohlcv/` snapshots.
- The daily production run accumulates any OHLCV frame it actually downloads
  into the same SQLite warehouse. `quant/run.py` first records the primary
  batched universe, then records extra tickers fetched on demand for paper
  sleeves and observation surfaces. Daily accumulation inserts missing rows by
  default and does not overwrite existing historical `(ticker, date)` rows, so
  fixed-window research rows are not silently rewritten by vendor adjusted-price
  drift. Set `OHLCV_WAREHOUSE_UPDATE_EXISTING=1` only for an intentional refresh
  run. `OHLCV_WAREHOUSE_PATH` can point the daily run at a different database,
  and `DISABLE_OHLCV_WAREHOUSE_ACCUMULATION=1` disables the side effect.
- Daily accumulation is not a full 10k-ticker vendor refresh. It guarantees
  that production-touched tickers keep accruing in the warehouse. Full raw
  `ticker_universe` refreshes should remain a separate batch/backfill job.
- Backtests can load the warehouse with `--ohlcv-warehouse`. A fixed-window
  before/after comparison must use the same OHLCV source on both sides:
  snapshot-vs-snapshot or warehouse-vs-warehouse, never mixed.
- A single `(ticker, date)` warehouse row cannot preserve multiple historical
  adjusted-price versions from overlapping snapshot lookback windows. Use
  `data/ohlcv/` snapshots when a legacy artifact needs bit-exact replay; use
  the warehouse for new broad-universe experiments and refresh baselines there.

## Broad-Universe Realized Fundamentals

`exp-20260605-007` pulled SEC Companyfacts and derived PIT-safe YoY growth for
the full broad 1,446 `all_windows_full_liquid` warehouse universe (vs the daily
sidecar's ~40 curated names). This is the clean, scalable, **free** alternative
to yfinance `eps_estimate` — which only covers ~50 curated names and is
annual/quarterly contaminated (`forwardEps` stored as if quarterly in
`data_layer._populate_from_info`). Companyfacts is **realized** fundamentals
(actuals + growth), not forward estimates, so it complements rather than
replaces an estimate-revision signal.

- Dataset: `data/kova/fundamentals/companyfacts_growth_broad_universe_YYYYMMDD.jsonl`
  (~124 MB, 199,887 growth rows; `growth_status == "ok"` for 137,642).
- Audit: `data/experiments/exp-20260605-007/broad_universe_companyfacts_coverage_audit.json`.
- Coverage of the 1,446 universe (as of 2026-06-04):
  - 88.6% have any fundamental facts; 80.9% revenue, 84.4% EPS.
  - **79.3% have a clean OK revenue YoY growth; 83.9% have OK EPS YoY growth.**
  - The ~11% gap is structural and expected: foreign filers / ADRs that file
    20-F in IFRS taxonomy (AZN, ASML, BABA, BP, BHP, ARM, BNTX, …) have no
    us-gaap XBRL, and index ETFs (SPY, QQQ, DIA, MDY) have no fundamentals.
- PIT semantics: `derive_companyfacts_growth_rows` drops any fact with
  `filed > asof`. Consumers must use only rows with `asof_date <= signal_date`.
- Rebuild / refresh (free official SEC API, ~14.5 min for 1,446 at the
  SEC-compliant 0.11s/request, cached under `data/cache/sec/companyfacts/`):
  `.\.venv\Scripts\python.exe quant\experiments\exp_20260605_007_broad_universe_companyfacts_asset.py`
- Source CIKs: 100% of the warehouse universe has a CIK
  (`ticker_universe.cik`); the fetcher resolves via `sec_ticker_map`.

## Placement Rules

1. Do not add new durable artifacts at `data/` root.
2. If a file is used by production or replay code, add or reuse a resolver in
   `quant/data_paths.py`.
3. If a file is per-experiment evidence, keep it under
   `data/experiments/<experiment_id>/`.
4. If a file is daily replay/production archive, place it under `data/daily/`
   or `data/non_ohlcv/` according to the table above.
5. Before deleting or moving duplicate-looking files, update hard-coded legacy
   path references and rerun the relevant backtest or audit command.

## Cleanup Order

1. Convert hard-coded legacy root paths to `quant/data_paths.py` resolvers.
2. Keep `data/README.md` as the directory-level operating guide and this file
   as the one-page map.
3. Only after resolver coverage is complete, archive or remove root-level
   duplicates with a commit that proves the affected tests/backtests still
   pass.
