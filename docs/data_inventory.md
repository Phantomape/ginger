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
| Broad/full ticker OHLCV warehouse | `data/experiments/exp-20260519-030/warehouse_main.sqlite` | Broad-market OHLCV warehouse built by `exp-20260519-030`. It has `ticker_universe`, broad `ohlcv`, versioned `ohlcv_snapshot_versions`, `fetch_status`, `coverage_summary`, and `run_manifest` tables; after the reference-asset seed the broad table contains 4,968,741 OHLCV rows and 1,446 `all_windows_full_liquid` tickers. Use broad `ohlcv` as the broad stock OHLCV research superset and preferred input for new full-universe work. Use `ohlcv_snapshot_versions` for standard fixed-window reproduction. `quant/ohlcv_warehouse.py` can seed deterministic snapshot rows, `quant/run.py` accumulates production-downloaded OHLCV into the broad table daily, and `quant/backtester.py --ohlcv-warehouse ...` can load either broad or versioned rows. |
| Non-OHLCV replay data | `data/non_ohlcv/` | SEC filings, filing text/features, Form 4, companyfacts, earnings/event snapshots, and coverage manifests. Check the coverage report before adding `require_non_ohlcv` rules. |
| Realized fundamentals (curated) | `data/kova/fundamentals/companyfacts_growth_YYYYMMDD.jsonl` | Daily Kova/CANSLIM sidecar SEC Companyfacts YoY growth for the ~40 curated trade-universe names. PIT-safe (`asof_date <= signal_date`). Built by `quant/kova_data_sidecar.py`. |
| Realized fundamentals (broad universe) | `data/kova/fundamentals/companyfacts_growth_broad_universe_YYYYMMDD.jsonl` | SEC Companyfacts realized YoY growth (revenue / eps_basic / eps_diluted / net_income) for the broad 1,446 `all_windows_full_liquid` warehouse universe. Built by `exp-20260605-007`. Free, official SEC XBRL, PIT-safe (filing date). See "Broad-Universe Realized Fundamentals" below for coverage. The clean, scalable alternative to yfinance `eps_estimate`, which is ~50-name-only and annual/quarterly contaminated. |
| Daily production archive | `data/daily/...` | News, signals, reports, LLM prompts/responses/decisions, earnings/event snapshots, universe state, and forward-test artifacts. Use `quant/data_paths.py` daily artifact helpers. |
| Operator-maintained live inputs | `operator_inputs/` | Manual/live inputs such as `open_positions.json` and `manual_trades.jsonl`. Gate 2 fields like `entry_date` and `target_price` are verified here, not under `data/`. |
| Backtest results | `data/backtests/backtest_results_*.json` | Standard backtest outputs. Keep top-level files for current/cited acceptance or audit summaries; archive bulky one-off comparison/per-window details under `data/backtests/archive/<date_or_topic>/`. Root-level `data/backtest_results_*.json` is legacy compatibility only. |
| Experiment artifacts | `data/experiments/exp-YYYYMMDD-NNN/` | Per-experiment outputs, diagnostics, and local snapshots. Experiment-local OHLCV copies are allowed only as that experiment's evidence and should not become shared inputs. |
| Paper sleeves | `data/paper_sleeves/<sleeve>/state.json` and `snapshots.jsonl` | Default-off paper sleeve state and forward snapshots. These are attribution/observation surfaces unless promoted through Gate 1-4. |
| Durable state, ledgers, reference | `data/state/`, `data/ledgers/`, `data/reference/` | Persistent state, append-only ledgers, and static reference maps. Prefer named keys in `quant/data_paths.py` for shared artifacts. |
| Diagnostics, cache, tmp | `data/diagnostics/`, `data/cache/`, `data/tmp/` | Local or diagnostic artifacts. They are not acceptance evidence unless explicitly cited in an experiment closeout. |

## OHLCV Duplication Rules

- The fixed-window backtester snapshot source of truth is `data/ohlcv/`.
- The broad stock OHLCV research superset is
  `data/experiments/exp-20260519-030/warehouse_main.sqlite`.
- The SQLite warehouse has two OHLCV roles:
  - `ohlcv`: one broad row per `(ticker, date)` for full-universe research and
    daily production accumulation.
  - `ohlcv_snapshot_versions`: one row per
    `(snapshot_source, ticker, date)` for fixed-window reproduction. This table
    preserves overlapping adjusted-price versions and prevents broader
    warehouse-only tickers from entering legacy standard baselines.
- Current shared files include three standard windows plus pilot/sleeve variants:
  `ohlcv_snapshot_20241002_20250422.json`,
  `ohlcv_snapshot_20250423_20251022.json`,
  `ohlcv_snapshot_20251023_20260421.json`,
  `ohlcv_snapshot_20251023_20260421_with_pilot_refreshed.json`, and
  `ohlcv_snapshot_20251023_20260501_with_pilot.json`.
- Some legacy experiment code still names `data/ohlcv_snapshot_*.json`.
  `quant/data_paths.py::ohlcv_snapshot_path` maps those names to
  `data/ohlcv/` when the organized file exists. New code should call that
  helper or pass the organized `data/ohlcv/...` path directly. The backtester
  also maps missing absolute legacy root paths like
  `...\data\ohlcv_snapshot_*.json` to `data/ohlcv/` so archived experiment
  runners survive the directory move without bulk rewrites.
- Do not bulk-edit historical experiment scripts only to replace snapshot
  strings. New standard fixed-window backtests should use the versioned SQLite
  warehouse, while file-oriented replay/probe/sidecar tools may keep explicit
  snapshot inputs when that is the intended interface.
- Experiment-local OHLCV snapshots under `data/experiments/<exp-id>/ohlcv/`
  are frozen evidence for that experiment only. Do not use them as future
  baselines unless a follow-up experiment promotes that exact artifact.
- The SQLite warehouse seeded the canonical stock snapshot rows and extends
  them to a much broader ticker set. Keep it aligned by running
  `.\.venv\Scripts\python.exe -B quant\ohlcv_warehouse.py seed-snapshots`
  after adding or changing deterministic `data/ohlcv/` snapshots.
- Keep the versioned fixed-window table aligned by running
  `.\.venv\Scripts\python.exe -B quant\ohlcv_warehouse.py seed-snapshot-versions`
  after adding or changing deterministic `data/ohlcv/` snapshots. Standard
  baseline runs from SQLite must pass
  `--ohlcv-warehouse-snapshot-source <SNAPSHOT>`.
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
- Hot/cold split (git-LFS churn fix): the cold warehouse
  `data/warehouse/warehouse_main.sqlite` is LFS-tracked, so upserting into it
  every run re-uploaded the whole ~700MB blob as a fresh LFS object daily. Daily
  and broad-refresh writes now land in a small sibling hot DB
  `data/warehouse/warehouse_main_hot.sqlite` (auto-LFS via the
  `data/warehouse/*.sqlite` glob, but tiny and growing slowly). Reads overlay
  hot on cold transparently — `load_warehouse_ohlcv_frames`,
  `connect_overlay_reader` (the `ohlcv_overlay` view), `warehouse_last_dates`,
  the universe-feed coverage scan, and `forward_replacement_value` comparator
  bars all see cold+hot, with hot winning on `(ticker, date)` conflicts. Callers
  keep passing the cold path; `quant/ohlcv_warehouse.py::hot_path_for` derives
  the sibling. Historical experiment replays read cold only — correct, since
  their fixed windows end before the hot boundary.
- Fold the hot tier back into cold once a window (~half a year) has accumulated:
  `.\.venv\Scripts\python.exe -B quant\ohlcv_warehouse.py merge-hot`
  (`INSERT OR IGNORE`, so cold's deterministic rows are never rewritten; then
  the hot DB is emptied and VACUUMed back to ~empty). Inspect pending hot rows
  with `... ohlcv_warehouse.py hot-status`. After a merge, commit the updated
  cold blob (one large LFS object per window) and the shrunk hot DB.
- Backtests can load the broad table with `--ohlcv-warehouse`, or a fixed
  snapshot version with both `--ohlcv-warehouse` and
  `--ohlcv-warehouse-snapshot-source`. A fixed-window before/after comparison
  must use the same OHLCV source on both sides: snapshot-vs-snapshot,
  versioned-SQLite-vs-versioned-SQLite, or broad-warehouse-vs-broad-warehouse;
  never mix them.
- Known retained snapshot consumers are intentional file-oriented tools:
  `quant/backtester.py --ohlcv-snapshot` for legacy exact-file replay;
  `scripts/run_options_forward_ledger.py`,
  `quant/gap_cancel_context_replay.py`, `quant/gap_cancel_threshold_sweep.py`,
  and `quant/kova_data_sidecar.py` for explicit snapshot sidecars; and
  observe-only probes such as `scripts/*_probe.py`,
  `scripts/audit_sector_state_alpha.py`, and
  `scripts/run_options_overlay_shadow.py` that inspect JSON bars directly.
  Do not use those retained file inputs as the default for new standard
  acceptance backtests unless the experiment explicitly documents that file
  replay is the causal variable.
- The 2026-06-04 warehouse-vs-snapshot investigation keeps only the compact
  versioned-SQLite parity summary and root-cause audit in top-level
  `data/backtests/`. The bulky per-window snapshot/current, broad-warehouse,
  and versioned-warehouse comparison outputs are archived under
  `data/backtests/archive/20260604_ohlcv_warehouse_replay/`.
- A single broad `(ticker, date)` warehouse row cannot preserve multiple
  historical adjusted-price versions from overlapping snapshot lookback
  windows. Use `data/ohlcv/` or `ohlcv_snapshot_versions` when a legacy
  artifact needs bit-exact replay; use broad `ohlcv` for new broad-universe
  experiments and refresh baselines there.

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
