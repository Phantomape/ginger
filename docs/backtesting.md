# Backtesting Commands

This file is the quick reference for running deterministic backtests used by
alpha experiments. General backtester usage is also documented in `AGENTS.md`
section 7, but the fixed-window snapshot commands are centralized here.

## Fixed Windows

Use these three windows when comparing strategy changes. They load saved OHLCV
snapshots so small yfinance download differences do not move the result.

```powershell
cd D:\Github\ginger

.\.venv\Scripts\python.exe quant\backtester.py --start 2025-10-23 --end 2026-04-21 --regime-aware-exit --ohlcv-snapshot data\ohlcv_snapshot_20251023_20260421.json

.\.venv\Scripts\python.exe quant\backtester.py --start 2025-04-23 --end 2025-10-22 --regime-aware-exit --ohlcv-snapshot data\ohlcv_snapshot_20250423_20251022.json

.\.venv\Scripts\python.exe quant\backtester.py --start 2024-10-02 --end 2025-04-22 --regime-aware-exit --ohlcv-snapshot data\ohlcv_snapshot_20241002_20250422.json
```

Window labels used in experiment logs:

| Label | Date range | Snapshot |
| --- | --- | --- |
| `late_strong` | `2025-10-23 -> 2026-04-21` | `data\ohlcv_snapshot_20251023_20260421.json` |
| `mid_weak` | `2025-04-23 -> 2025-10-22` | `data\ohlcv_snapshot_20250423_20251022.json` |
| `old_thin` | `2024-10-02 -> 2025-04-22` | `data\ohlcv_snapshot_20241002_20250422.json` |

## Current Live Sanity Windows

Use these after a fixed-window result looks positive. They do not use snapshots,
so treat them as sanity checks rather than the primary acceptance evidence.

```powershell
cd D:\Github\ginger

.\.venv\Scripts\python.exe quant\backtester.py --start 2025-10-27 --end 2026-04-24 --regime-aware-exit

.\.venv\Scripts\python.exe quant\backtester.py --start 2025-04-28 --end 2025-10-24 --regime-aware-exit
```

## Save A New Snapshot

Only create a new snapshot when intentionally changing the fixed comparison set.
Record why in `docs/experiment_log.jsonl`.

```powershell
cd D:\Github\ginger

.\.venv\Scripts\python.exe quant\backtester.py --start YYYY-MM-DD --end YYYY-MM-DD --regime-aware-exit --save-ohlcv-snapshot data\ohlcv_snapshot_YYYYMMDD_YYYYMMDD.json
```

## Plain Backtest

For a quick non-deterministic run using fresh market data:

```powershell
cd D:\Github\ginger

.\.venv\Scripts\python.exe quant\backtester.py --start YYYY-MM-DD --end YYYY-MM-DD --regime-aware-exit
```

## High-Importance Metrics

The backtester emits these extra measurement fields for alpha experiments:

| Field | Why it matters |
| --- | --- |
| `capital_efficiency` | Shows return/PnL per trade and per calendar slot-day, so a strategy that ties up capital for too long is visible even if total return looks fine. |
| `sizing_rule_signal_attribution` | Counts how often each risk multiplier touched candidate signals, including zero-risk signals that never became trades. |
| `sizing_rule_trade_attribution` | Shows observed trade outcomes for positions that carried non-neutral sizing multipliers. This is attribution, not a counterfactual PnL claim. |
| `single_window_quality` | Summarizes whether the current window is positive on EV, return, daily Sharpe, and drawdown guardrails. |
| `multi_window_robustness` | Added to cross-window diagnostics; summarizes positive windows, EV spread, worst drawdown, and an observation-only robustness score. |
