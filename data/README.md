# Data Directory Layout

This directory is intentionally partly flat because production and replay code
look up several files by exact `data/<name>_YYYYMMDD.ext` patterns.

## Keep At Data Root

Do not move these without updating the readers first:

- `backtest_results_YYYYMMDD.json`
- `news_YYYYMMDD.json`
- `clean_news_YYYYMMDD.json`
- `clean_trade_news_YYYYMMDD.json`
- `earnings_snapshot_YYYYMMDD.json`
- `llm_prompt_YYYYMMDD.txt`
- `llm_prompt_resp_YYYYMMDD.json`
- `llm_decision_log_YYYYMMDD.json`
- `quant_signals_YYYYMMDD.json`
- `trend_signals_YYYYMMDD.json`
- `report_YYYYMMDD.txt`
- `ohlcv_snapshot_*.json`
- generated state files such as `pending_actions.json` and
  `universe_registry.json`

Manual operator-maintained inputs now live in `../operator_inputs/`, especially
`open_positions.json` and `manual_trades.jsonl`.

## Subdirectories

- `data/experiments/`: large experiment outputs keyed by experiment id.
- `data/non_ohlcv/`: SEC, Form 4, companyfacts, and other external data.
- `data/tmp/`: local temporary indexes and scratch files; ignored by git.
- `data/*_cache/`: local fetch/cache directories; ignored by git where
  appropriate.

If a new artifact is only useful for one experiment, put it under
`data/experiments/<experiment_id>/`. If production or replay code needs it by
date, keep it at the root until the code has a shared archive adapter.
