# Data Directory Layout

`data/` is organized by artifact role. Daily production archives live under
`data/daily/`; long-lived state, caches, and fixed historical compatibility
anchors may remain at the root.

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
- `daily/snapshots/earnings/`: `earnings_snapshot_YYYYMMDD.json`
- `daily/snapshots/events/`: `event_snapshot_YYYYMMDD.json`
- `daily/universe/`: `universe_state_YYYYMMDD.json`
- `daily/forward_tests/`: `forward_test_YYYYMMDD.json` and
  `strategy_attribution_YYYYMMDD.json`

Production/replay code should use `quant/data_paths.py` instead of hard-coding
these paths. The resolver prefers the organized path and falls back to the
legacy root filename for older checkouts or custom test directories.

## Other Directories

- `backtests/`: new `backtest_results_*.json` outputs.
- `diagnostics/`: ad hoc audits and oracle/diagnostic artifacts.
- `experiments/`: experiment outputs keyed by experiment id.
- `experiments/legacy-root/`: old root-level `exp*` files moved out of the
  data root without changing their contents.
- `non_ohlcv/`: SEC, Form 4, companyfacts, and other external data.
- `tmp/`: local temporary indexes and scratch files; ignored by git.
- `*_cache/`: local fetch/cache directories; ignored by git where appropriate.

## Root Compatibility Anchors

Keep root-level files that are shared state or heavily referenced by historical
experiments, including:

- `pending_actions.json`
- `universe_registry.json`
- `universe_events.jsonl`
- `sec_company_tickers.json`
- `ohlcv_snapshot_*.json`
- existing `backtest_results_*.json`

Manual operator-maintained inputs live in `../operator_inputs/`, especially
`open_positions.json` and `manual_trades.jsonl`.
