# Data Directory Layout

`data/` is organized by artifact role. Daily production archives live under
`data/daily/`; durable state, ledgers, snapshots, and experiment outputs live
in named subdirectories. The root should stay limited to this README.

## Daily Archives

- `daily/news/raw/`: `news_YYYYMMDD.json`
- `daily/news/source_stats/`: `news_source_stats_YYYYMMDD.json`
- `daily/news/clean/`: `clean_news_YYYYMMDD.json`
- `daily/news/trade/`: `clean_trade_news_YYYYMMDD.json`
- `daily/signals/quant/`: `quant_signals_YYYYMMDD.json`
- `daily/signals/trend/`: `trend_signals_YYYYMMDD.json`
- `daily/reports/`: `report_YYYYMMDD.txt`
- `daily/llm/prompts/`: `llm_prompt_YYYYMMDD.txt`
- `daily/llm/responses/`: `llm_prompt_resp_YYYYMMDD.json`
- `daily/llm/decisions/`: `llm_decision_log_YYYYMMDD.json`
- `daily/llm/advice/`: `investment_advice_YYYYMMDD.json`
- `daily/llm/raw/`: `llm_output_YYYYMMDD.json`
- `daily/snapshots/earnings/`: canonical `earnings_snapshot_YYYYMMDD.json`
  files. `daily/snapshots/earnings/legacy_root/` preserves older root-level
  snapshots whose content differs from the canonical file for the same date;
  resolvers do not load that legacy archive.
- `daily/snapshots/events/`: `event_snapshot_YYYYMMDD.json`
- `daily/universe/`: `universe_state_YYYYMMDD.json`
- `daily/forward_tests/`: `forward_test_YYYYMMDD.json` and
  `strategy_attribution_YYYYMMDD.json`

Production/replay code should use `quant/data_paths.py` instead of hard-coding
these paths. The resolver prefers the organized path and falls back to the
legacy root filename for older checkouts or custom test directories.

## Other Directories

- `backtests/`: new `backtest_results_*.json` outputs.
- `cache/`: local API/vendor caches, grouped by provider/domain and ignored
  by git.
- `diagnostics/`: ad hoc audits and oracle/diagnostic artifacts.
- `experiments/`: experiment outputs keyed by experiment id.
- `experiments/current/`: current aggregate experiment/audit views that are
  not tied to one experiment id.
- `ledgers/`: append-only operational ledgers, such as pilot competition
  decisions.
- `non_ohlcv/`: SEC, Form 4, companyfacts, and other external data.
- `ohlcv/`: deterministic OHLCV snapshots used by standard replay windows.
- `paper_sleeves/`: default-off paper sleeve state and snapshot logs, grouped
  by sleeve name.
- `reference/`: reusable static or cached reference data, such as SEC ticker
  maps.
- `state/`: durable operator or production state, grouped by domain.
- `tmp/`: local temporary indexes and scratch files; ignored by git.

## Root Compatibility Anchors

Do not add new root-level data artifacts. Production/replay code should use
`quant/data_paths.py`, whose resolvers prefer the organized paths and fall
back to legacy root filenames for older checkouts or custom test directories.
If a legacy root daily artifact duplicates a canonical organized artifact but
has different content, move it under the relevant canonical archive directory
instead of leaving it in `data/`.

Manual operator-maintained inputs live in `../operator_inputs/`, especially
`open_positions.json` and `manual_trades.jsonl`.
