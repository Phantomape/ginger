"""Build SPACE_CATALYST_SHADOW OHLCV-augmented snapshots.

This is a data-coverage experiment only. It copies the canonical fixed-window
OHLCV snapshots and appends the current space-catalyst shadow tickers so the
theme can be replayed without mutating the accepted core snapshots.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260510-028"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

SPACE_CATALYST_TICKERS = [
    "RKLB",
    "ASTS",
    "LUNR",
    "HAWK",
    "PL",
    "RDW",
    "BKSY",
    "IRDM",
    "VSAT",
    "GSAT",
    "SATS",
    "ARKX",
    "UFO",
    "SPCE",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_date(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _snapshot_fetch_bounds(snapshot: dict[str, Any]) -> tuple[str, str]:
    metadata = snapshot.get("metadata") or {}
    start = metadata.get("download_start")
    end = metadata.get("download_end")
    if start and end:
        return str(start), str(end)

    dates: list[str] = []
    for rows in (snapshot.get("ohlcv") or {}).values():
        for row in rows or []:
            date = row.get("Date")
            if date:
                dates.append(str(date))
    if not dates:
        raise ValueError("snapshot has no metadata download bounds or row dates")
    return min(dates), max(dates)


def _finite_float(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _fetch_yahoo_adjusted_rows(ticker: str, start: str, end: str) -> list[dict[str, Any]]:
    start_dt = _parse_date(start)
    # Yahoo chart period2 is exclusive. Add one day so a weekday end is included.
    end_dt = _parse_date(end) + timedelta(days=1)
    period1 = int(start_dt.timestamp())
    period2 = int(end_dt.timestamp())
    encoded = urllib.parse.quote(ticker)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={period1}&period2={period2}&interval=1d"
        "&events=history&includeAdjustedClose=true"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    chart = payload.get("chart") or {}
    error = chart.get("error")
    if error:
        raise RuntimeError(error)
    result = (chart.get("result") or [None])[0]
    if not result:
        return []

    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quote = (indicators.get("quote") or [{}])[0]
    adj = (indicators.get("adjclose") or [{}])[0].get("adjclose") or []

    rows: list[dict[str, Any]] = []
    for idx, ts in enumerate(timestamps):
        raw_close = _finite_float((quote.get("close") or [None])[idx])
        adj_close = _finite_float(adj[idx] if idx < len(adj) else None)
        open_ = _finite_float((quote.get("open") or [None])[idx])
        high = _finite_float((quote.get("high") or [None])[idx])
        low = _finite_float((quote.get("low") or [None])[idx])
        volume = _finite_float((quote.get("volume") or [None])[idx])
        if raw_close is None or adj_close is None or open_ is None or high is None or low is None:
            continue
        ratio = adj_close / raw_close if raw_close else 1.0
        rows.append(
            {
                "Date": datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat(),
                "Open": float(open_ * ratio),
                "High": float(high * ratio),
                "Low": float(low * ratio),
                "Close": float(adj_close),
                "Volume": float(volume or 0.0),
            }
        )
    rows.sort(key=lambda row: row["Date"])
    return rows


def _output_snapshot_path(label: str) -> Path:
    return (
        REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / "ohlcv"
        / f"{EXPERIMENT_ID}_{label}_with_space_catalyst.json"
    )


def build_snapshots() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "change_type": "ohlcv_snapshot_coverage_expansion",
        "changed_variable": "append_space_catalyst_shadow_tickers_to_snapshot_copies",
        "source": "Yahoo Finance chart API adjusted OHLC",
        "tickers_requested": SPACE_CATALYST_TICKERS,
        "windows": {},
        "notes": [
            "Canonical OHLCV snapshots are not modified.",
            "SPACE_CATALYST_SHADOW remains observe-only; these rows do not enable live slots.",
            "HAWK or other recent listings may have partial or zero history in older windows.",
        ],
    }

    for label, spec in WINDOWS.items():
        source_path = REPO_ROOT / spec["snapshot"]
        snapshot = _load_json(source_path)
        ohlcv = snapshot.setdefault("ohlcv", {})
        fetch_start, fetch_end = _snapshot_fetch_bounds(snapshot)

        added: list[str] = []
        already_present: list[str] = []
        failures: dict[str, str] = {}
        row_counts: dict[str, int] = {}

        for ticker in SPACE_CATALYST_TICKERS:
            if ticker in ohlcv and ohlcv[ticker]:
                already_present.append(ticker)
                row_counts[ticker] = len(ohlcv[ticker])
                continue
            try:
                rows = _fetch_yahoo_adjusted_rows(ticker, fetch_start, fetch_end)
            except Exception as exc:  # pragma: no cover - network/provider behavior
                failures[ticker] = str(exc)
                rows = []
            if rows:
                ohlcv[ticker] = rows
                added.append(ticker)
                row_counts[ticker] = len(rows)
            else:
                row_counts[ticker] = 0
                failures.setdefault(ticker, "no rows returned")
            time.sleep(0.15)

        metadata = snapshot.setdefault("metadata", {})
        prior_augments = metadata.get("space_catalyst_augments") or []
        metadata.update(
            {
                "space_catalyst_augmented": True,
                "space_catalyst_augmented_at": generated_at,
                "space_catalyst_source": "Yahoo Finance chart API adjusted OHLC",
                "space_catalyst_source_snapshot": spec["snapshot"],
                "space_catalyst_added_tickers": added,
                "space_catalyst_already_present_tickers": already_present,
                "space_catalyst_failed_tickers": sorted(failures),
                "ticker_count": len(ohlcv),
                "tickers": sorted(ohlcv),
                "space_catalyst_augments": [
                    *prior_augments,
                    {
                        "experiment_id": EXPERIMENT_ID,
                        "generated_at": generated_at,
                        "tickers_requested": SPACE_CATALYST_TICKERS,
                    },
                ],
            }
        )

        output_path = _output_snapshot_path(label)
        _write_json(output_path, snapshot)
        manifest["windows"][label] = {
            "date_range": f"{spec['start']} -> {spec['end']}",
            "source_snapshot": spec["snapshot"],
            "augmented_snapshot": str(output_path.relative_to(REPO_ROOT)),
            "fetch_range": f"{fetch_start} -> {fetch_end}",
            "source_ticker_count": len((_load_json(source_path).get("ohlcv") or {})),
            "augmented_ticker_count": len(ohlcv),
            "added_tickers": added,
            "already_present_tickers": already_present,
            "failed_tickers": failures,
            "row_counts": row_counts,
        }

    manifest_path = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / "space_catalyst_ohlcv_snapshot_build.json"
    _write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    manifest = build_snapshots()
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
