"""exp-20260706-003: deep index drawdown episode ETF rebound (default-off paper).

Subcommands:

  backfill  Fetch pre-warehouse (2000-01-01 .. 2023-08-28) daily OHLCV for the
            index/context tickers from yfinance and materialize the PIT archive
            data/non_ohlcv/index_history/index_daily_pre2023.jsonl (+ manifest).
            One-time evidence construction for this experiment; the daily sleeve
            does not depend on the archive.

  replay    Merge the archive with the OHLCV warehouse QQQ series and replay the
            fixed policy bundle over the full history; write the episode-level
            artifact to data/experiments/exp-20260706-003/.

Reproduce:
  .venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260706_003_deep_drawdown_rebound.py backfill
  .venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260706_003_deep_drawdown_rebound.py replay
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT = REPO_ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from data_paths import DATA_ROOT, atomic_write_json  # noqa: E402
from deep_drawdown_rebound_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    INDEX_HISTORY_PATH,
    RULE_VERSION,
    load_index_history_rows,
    merge_bar_series,
    replay_deep_drawdown_rebound_trades,
    summarize_replay_trades,
)

EXPERIMENT_ID = "exp-20260706-003"
ARCHIVE_TICKERS = ("QQQ", "SPY", "^VIX", "TLT")
ARCHIVE_START = "2000-01-01"
ARCHIVE_END = "2023-08-28"  # warehouse coverage starts 2023-08-29
MANIFEST_PATH = INDEX_HISTORY_PATH.parent / "source_manifest.json"
ARTIFACT_PATH = (
    DATA_ROOT / "experiments" / EXPERIMENT_ID / "exp_20260706_003_deep_drawdown_rebound.json"
)
WAREHOUSE_PATHS = (
    DATA_ROOT / "warehouse" / "warehouse_main.sqlite",
    DATA_ROOT / "tmp" / "warehouse_main_alpha_search_readcopy.sqlite",
)

STANDARD_WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cmd_backfill() -> int:
    from yfinance_bootstrap import configure_yfinance_runtime

    configure_yfinance_runtime()
    import yfinance as yf

    INDEX_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    coverage: dict[str, dict] = {}
    for ticker in ARCHIVE_TICKERS:
        frame = yf.download(
            ticker,
            start=ARCHIVE_START,
            end=ARCHIVE_END,
            auto_adjust=True,
            progress=False,
        )
        if frame is None or frame.empty:
            coverage[ticker] = {"rows": 0, "status": "empty"}
            continue
        if hasattr(frame.columns, "get_level_values") and frame.columns.nlevels > 1:
            frame.columns = frame.columns.get_level_values(0)
        count = 0
        first = last = None
        for idx, row in frame.iterrows():
            date = str(idx)[:10]
            record = {
                "ticker": ticker.upper(),
                "date": date,
                "open": round(float(row["Open"]), 6),
                "high": round(float(row["High"]), 6),
                "low": round(float(row["Low"]), 6),
                "close": round(float(row["Close"]), 6),
                "volume": float(row["Volume"]) if row["Volume"] == row["Volume"] else None,
            }
            lines.append(json.dumps(record, sort_keys=True))
            count += 1
            last = date
            first = first or date
        coverage[ticker] = {"rows": count, "first_date": first, "last_date": last, "status": "ok"}
        print(f"[backfill] {ticker}: {count} rows {first} -> {last}")

    tmp = INDEX_HISTORY_PATH.with_suffix(".jsonl.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(INDEX_HISTORY_PATH)
    atomic_write_json(
        {
            "experiment_id": EXPERIMENT_ID,
            "source": "yfinance daily download, auto_adjust=True (split+dividend adjusted OHLC)",
            "requested_range": {"start": ARCHIVE_START, "end": ARCHIVE_END},
            "reason": (
                "OHLCV warehouse coverage starts 2023-08-29; deep-drawdown episode "
                "evidence (2000-2023: dot-com, GFC 2008, 2011, 2015-16, 2018Q4, "
                "2020 COVID, 2022 bear) only exists pre-warehouse."
            ),
            "point_in_time_note": (
                "Backfilled once from a live vendor on the fetch date; rows are "
                "historical daily bars, not restated in-repo afterwards. Adjusted "
                "series: drawdown percentages differ slightly from unadjusted "
                "price drawdowns."
            ),
            "fetched_at": _utc_now(),
            "coverage": coverage,
            "row_count": len(lines),
        },
        MANIFEST_PATH,
    )
    print(f"[backfill] wrote {len(lines)} rows -> {INDEX_HISTORY_PATH}")
    return 0


def _warehouse_rows(ticker: str) -> tuple[list[dict], str]:
    last_error = None
    for path in WAREHOUSE_PATHS:
        if not path.exists():
            continue
        uri = f"file:{path.as_posix()}?mode=ro"
        try:
            con = sqlite3.connect(uri, uri=True, timeout=10)
            try:
                rows = con.execute(
                    "select date, open, high, low, close, volume from ohlcv "
                    "where ticker=? order by date",
                    (ticker,),
                ).fetchall()
            finally:
                con.close()
            return (
                [
                    {
                        "ticker": ticker,
                        "date": r[0],
                        "open": r[1],
                        "high": r[2],
                        "low": r[3],
                        "close": r[4],
                        "volume": r[5],
                    }
                    for r in rows
                ],
                str(path),
            )
        except sqlite3.OperationalError as exc:  # locked/contended: try fallback copy
            last_error = exc
            continue
    raise RuntimeError(f"no readable warehouse for {ticker}: {last_error}")


def _window_slice(trades: list[dict], start: str, end: str) -> dict:
    rows = [t for t in trades if start <= str(t.get("entry_date")) <= end]
    return summarize_replay_trades(rows)


def cmd_replay() -> int:
    ticker = str(DEFAULT_CONFIG["ticker"]).upper()
    archive_rows = load_index_history_rows(ticker)
    if not archive_rows:
        print("[replay] archive missing; run backfill first", file=sys.stderr)
        return 2
    warehouse_rows, warehouse_path = _warehouse_rows(ticker)
    merged = merge_bar_series(archive_rows, warehouse_rows)
    result = replay_deep_drawdown_rebound_trades(merged)
    trades = result["trades"]

    # SPY same-window buy-and-hold context per trade (replacement-value axis).
    spy_archive = load_index_history_rows("SPY")
    spy_warehouse, _ = _warehouse_rows("SPY")
    spy = merge_bar_series(spy_archive, spy_warehouse)
    spy_close = {row["date"]: row["close"] for row in spy if row.get("close")}
    for trade in trades:
        entry_close = spy_close.get(trade.get("entry_date"))
        exit_close = spy_close.get(trade.get("exit_date"))
        if entry_close and exit_close:
            spy_ret = (float(exit_close) / float(entry_close)) - 1.0
            trade["spy_same_window_return_pct"] = round(spy_ret, 6)
            trade["excess_vs_spy_pct"] = round(
                (trade.get("pnl_pct_net") or 0.0) - spy_ret, 6
            )

    closed = [t for t in trades if t.get("paper_status") == "closed"]
    excess = [
        t["excess_vs_spy_pct"] for t in closed if t.get("excess_vs_spy_pct") is not None
    ]
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "generated_at": _utc_now(),
        "series": {
            "ticker": ticker,
            "archive_rows": len(archive_rows),
            "warehouse_rows": len(warehouse_rows),
            "warehouse_path": warehouse_path,
            "merged_rows": len(merged),
            "first_date": merged[0]["date"] if merged else None,
            "last_date": merged[-1]["date"] if merged else None,
        },
        "parameters": result["parameters"],
        "summary": result["summary"],
        "spy_replacement": {
            "trades_with_spy_context": len(excess),
            "mean_excess_vs_spy_pct": round(sum(excess) / len(excess), 6) if excess else None,
            "positive_excess_count": sum(1 for e in excess if e > 0),
        },
        "standard_windows": {
            name: _window_slice(trades, start, end)
            for name, (start, end) in STANDARD_WINDOWS.items()
        },
        "trades": trades,
        "unresolved": result["unresolved"],
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(artifact, ARTIFACT_PATH)
    summary = result["summary"]
    print(
        f"[replay] {summary['closed_trades']} closed trades across "
        f"{summary['distinct_episodes']} episodes; total pnl ${summary['total_pnl']}, "
        f"win rate {summary['win_rate']}, mean {summary['mean_return_pct']}, "
        f"median {summary['median_return_pct']}, worst {summary['worst_return_pct']}"
    )
    print(f"[replay] artifact -> {ARTIFACT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["backfill", "replay"])
    args = parser.parse_args()
    if args.command == "backfill":
        return cmd_backfill()
    return cmd_replay()


if __name__ == "__main__":
    raise SystemExit(main())
