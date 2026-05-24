# Earnings Snapshot Archive

Canonical daily earnings replay snapshots live directly in this directory:

```text
earnings_snapshot_YYYYMMDD.json
```

Production and replay code should reach these files through
`quant/data_paths.py` (`daily_artifact_path`, `resolve_daily_artifact_path`, or
`daily_artifact_glob`) instead of hard-coding `data/earnings_snapshot_*.json`.

`legacy_root/` is an audit-only holding area for old root-level snapshots whose
content differs from the canonical organized file for the same date. It is not
included by `daily_artifact_glob("earnings_snapshot")`, so files there do not
change backtest or production replay behavior.
