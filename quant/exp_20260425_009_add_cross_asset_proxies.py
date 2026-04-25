"""Add missing cross-asset ETF proxy OHLCV rows to fixed snapshots.

This is alpha-enabling data work for the macro information-source branch. It
does not alter production logic or existing snapshot tickers; it only appends
missing ETF proxy histories using each snapshot's recorded download window.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from yfinance_bootstrap import configure_yfinance_runtime  # noqa: E402


SNAPSHOTS = [
    REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
    REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
    REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
]

PROXIES = ["TLT", "IEF", "UUP", "USO", "XLE", "XLU", "XLP", "XLV"]


def _download_rows(ticker: str, start: str, end: str):
    df = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,
    )
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Volume"]
    if any(col not in df.columns for col in required):
        return []
    rows = []
    for idx, row in df.iterrows():
        rows.append({
            "Date": str(pd.Timestamp(idx).date()),
            "Open": float(row["Open"]),
            "High": float(row["High"]),
            "Low": float(row["Low"]),
            "Close": float(row["Close"]),
            "Volume": float(row["Volume"]),
        })
    return rows


def _augment_snapshot(path: Path):
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    metadata = payload.get("metadata") or {}
    ohlcv = payload.setdefault("ohlcv", {})
    start = metadata.get("download_start")
    end = metadata.get("download_end")
    if not start or not end:
        raise ValueError(f"Snapshot missing download_start/download_end: {path}")

    added = {}
    skipped_present = []
    failed = []
    for ticker in PROXIES:
        if ticker in ohlcv:
            skipped_present.append(ticker)
            continue
        rows = _download_rows(ticker, start, end)
        if not rows:
            failed.append(ticker)
            continue
        ohlcv[ticker] = rows
        added[ticker] = len(rows)

    tickers = sorted(ohlcv.keys())
    metadata["tickers"] = tickers
    metadata["cross_asset_proxies_added"] = sorted(
        set(metadata.get("cross_asset_proxies_added", [])) | set(added.keys())
    )
    payload["metadata"] = metadata

    if added:
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    return {
        "snapshot": str(path.relative_to(REPO_ROOT)),
        "download_start": start,
        "download_end": end,
        "added": added,
        "skipped_present": skipped_present,
        "failed": failed,
    }


def main() -> int:
    configure_yfinance_runtime()
    results = []
    for path in SNAPSHOTS:
        result = _augment_snapshot(path)
        results.append(result)
        print(
            f"{result['snapshot']}: added={result['added']} "
            f"failed={result['failed']} present={result['skipped_present']}"
        )
    out = REPO_ROOT / "data" / "exp_20260425_009_proxy_snapshot_augmentation.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump({"results": results}, f, indent=2)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
