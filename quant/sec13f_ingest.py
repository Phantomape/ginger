"""Universe-scoped SEC 13F institutional-holdings ingestion.

exp-20260613-007: download the latest available SEC Form 13F structured data
set, map holdings to tickers via the universe-scoped issuer-name CUSIP map, and
write real per-ticker institutional aggregates for the broad universe.

13F is quarterly data published in ~3-month filing windows, so ingestion is
idempotent per window: a daily call is a no-op once the current window's output
exists, and only re-parses when a new window is released (~4x/year). SEC
switched the dataset URL from ``{year}q{quarter}_form13f.zip`` to a
filing-window name (``01mar2026-31may2026_form13f.zip``) around 2024; this
module builds the window URL and falls back to the previous window near a
release boundary.

Data-only: no signals, orders, ranking, sizing or exits. Writes to
``data/non_ohlcv/sec13f_institutional/`` and never touches the kova path.
"""

from __future__ import annotations

import calendar
import json
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from data_paths import atomic_write_json, data_artifact_path
    from kova_data_sidecar import DEFAULT_USER_AGENT, parse_sec13f_zip
    from sec13f_universe_map import (
        build_cusip_ticker_map,
        load_company_name_index,
        normalize_issuer_name,
    )
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant.data_paths import atomic_write_json, data_artifact_path
    from quant.kova_data_sidecar import DEFAULT_USER_AGENT, parse_sec13f_zip
    from quant.sec13f_universe_map import (
        build_cusip_ticker_map,
        load_company_name_index,
        normalize_issuer_name,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec13f_institutional"
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec13f_institutional" / "source_cache"
URL_BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets"
RULE_VERSION = "sec13f_universe_name_match_v1"

_MONTH_ABBR = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
]
# Filing windows start in these months and run for three calendar months.
_WINDOW_START_MONTHS = (3, 6, 9, 12)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_of_date(as_of: Any = None) -> date:
    if as_of is None:
        return datetime.now(timezone.utc).date()
    if isinstance(as_of, date) and not isinstance(as_of, datetime):
        return as_of
    return date.fromisoformat(str(as_of)[:10])


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _window_bounds(start_year: int, start_month: int) -> tuple[date, date]:
    end_month = start_month + 2
    end_year = start_year
    if end_month > 12:
        end_month -= 12
        end_year += 1
    return date(start_year, start_month, 1), date(end_year, end_month, _last_day(end_year, end_month))


def window_label(start_year: int, start_month: int) -> str:
    start, end = _window_bounds(start_year, start_month)
    return (
        f"{start.day:02d}{_MONTH_ABBR[start.month - 1]}{start.year}"
        f"-{end.day:02d}{_MONTH_ABBR[end.month - 1]}{end.year}"
    )


def window_url(start_year: int, start_month: int) -> str:
    return f"{URL_BASE}/{window_label(start_year, start_month)}_form13f.zip"


def _recent_windows(as_of: date, *, back: int = 6) -> list[tuple[int, int]]:
    """Window (start_year, start_month) pairs whose end <= as_of, newest first."""
    windows: list[tuple[date, int, int]] = []
    for year in (as_of.year, as_of.year - 1, as_of.year - 2):
        for month in _WINDOW_START_MONTHS:
            _, end = _window_bounds(year, month)
            if end <= as_of:
                windows.append((end, year, month))
    windows.sort(reverse=True)
    return [(year, month) for _end, year, month in windows[:back]]


def latest_available_window(
    as_of: Any = None,
    *,
    head_check: Callable[[str], bool] | None = None,
) -> tuple[int, int]:
    """Return the (start_year, start_month) of the newest published window.

    Without ``head_check`` returns the newest window whose end date has passed.
    With ``head_check`` (a URL->bool availability probe) walks back to the first
    window that actually exists, which absorbs publish lag near a boundary.
    """
    candidates = _recent_windows(_as_of_date(as_of))
    if not candidates:
        raise RuntimeError("no 13F filing window precedes the given date")
    if head_check is None:
        return candidates[0]
    for year, month in candidates:
        if head_check(window_url(year, month)):
            return year, month
    return candidates[0]


def _default_head_check(url: str) -> bool:
    request = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": DEFAULT_USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def _default_download(url: str, dest: Path) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.read())
    return dest


def aggregate_universe_holdings(
    holding_rows: Iterable[dict[str, Any]],
    *,
    name_index: dict[str, str],
    universe: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Single pass: per-ticker institutional aggregates + the CUSIP->ticker map.

    Holdings are matched to a ticker directly via normalized issuer name; only
    universe tickers are aggregated. Returns ``(by_ticker, cusip_ticker_map)``.
    """
    allowed = {str(t).upper() for t in universe}
    managers: dict[str, set[str]] = defaultdict(set)
    agg: dict[str, dict[str, Any]] = {}
    cusip_map: dict[str, str] = {}
    cusip_conflicts: set[str] = set()
    for row in holding_rows:
        ticker = name_index.get(normalize_issuer_name(row.get("name_of_issuer")))
        if not ticker or ticker not in allowed:
            continue
        cusip = str(row.get("cusip") or "").upper().replace(" ", "")
        if cusip and cusip not in cusip_conflicts:
            existing = cusip_map.get(cusip)
            if existing and existing != ticker:
                cusip_conflicts.add(cusip)
                cusip_map.pop(cusip, None)
            else:
                cusip_map.setdefault(cusip, ticker)

        entry = agg.get(ticker)
        if entry is None:
            entry = {
                "ticker": ticker,
                "holder_count": 0,
                "position_row_count": 0,
                # SEC reports the 13F VALUE column in whole dollars since 2023
                # (the upstream parser key value_usd_thousands is legacy-named).
                "total_value_usd": 0.0,
                "total_shares": 0.0,
                "report_period": row.get("report_period"),
            }
            agg[ticker] = entry
        entry["position_row_count"] += 1
        value = row.get("value_usd_thousands")
        shares = row.get("shares")
        if isinstance(value, (int, float)):
            entry["total_value_usd"] += float(value)
        if isinstance(shares, (int, float)):
            entry["total_shares"] += float(shares)
        manager = str(row.get("manager_cik") or row.get("manager_name") or "").strip()
        if manager:
            managers[ticker].add(manager)

    for ticker, entry in agg.items():
        entry["holder_count"] = len(managers.get(ticker, ()))
        entry["total_value_usd"] = round(entry["total_value_usd"], 2)
        entry["total_shares"] = round(entry["total_shares"], 2)
    return agg, cusip_map


def ingest_universe_13f(
    *,
    universe: Iterable[str],
    as_of: Any = None,
    out_dir: Path | str = DEFAULT_OUT_DIR,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    company_tickers_path: Path | str | None = None,
    head_check: Callable[[str], bool] | None = _default_head_check,
    download: Callable[[str, Path], Path] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Idempotently ingest the latest available 13F window for the universe."""
    universe_set = {str(t).upper() for t in universe if str(t).strip()}
    out_root = Path(out_dir)
    cache_root = Path(cache_dir)
    as_of_date = _as_of_date(as_of)

    year, month = latest_available_window(as_of_date, head_check=head_check)
    label = window_label(year, month)
    holdings_path = out_root / f"holdings_{label}.json"
    pointer_path = out_root / "latest.json"

    if holdings_path.exists() and not force:
        summary = {
            "status": "current",
            "rule_version": RULE_VERSION,
            "as_of": as_of_date.isoformat(),
            "window_label": label,
            "holdings_path": str(holdings_path),
            "reused_existing": True,
            "generated_at": _utc_now_iso(),
        }
        _write_pointer(pointer_path, summary)
        return summary

    downloader = download or _default_download
    zip_path = cache_root / f"{label}_form13f.zip"
    if not zip_path.exists():
        downloader(window_url(year, month), zip_path)

    name_index = load_company_name_index(company_tickers_path)
    rows = parse_sec13f_zip(zip_path, asof_date=as_of_date.isoformat(), cusip_ticker_map=None)
    by_ticker, cusip_map = aggregate_universe_holdings(
        rows, name_index=name_index, universe=universe_set
    )

    payload = {
        "status": "ingested",
        "rule_version": RULE_VERSION,
        "as_of": as_of_date.isoformat(),
        "window_label": label,
        "window_url": window_url(year, month),
        "generated_at": _utc_now_iso(),
        "universe_size": len(universe_set),
        "universe_covered_count": len(by_ticker),
        "universe_coverage_pct": round(100.0 * len(by_ticker) / len(universe_set), 1)
        if universe_set
        else 0.0,
        "cusip_map_size": len(cusip_map),
        "holdings": sorted(by_ticker.values(), key=lambda r: r["ticker"]),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, holdings_path)

    summary = {
        "status": "ingested",
        "rule_version": RULE_VERSION,
        "as_of": as_of_date.isoformat(),
        "window_label": label,
        "holdings_path": str(holdings_path),
        "universe_size": payload["universe_size"],
        "universe_covered_count": payload["universe_covered_count"],
        "universe_coverage_pct": payload["universe_coverage_pct"],
        "reused_existing": False,
        "generated_at": payload["generated_at"],
    }
    _write_pointer(pointer_path, summary)
    return summary


def _write_pointer(pointer_path: Path, summary: dict[str, Any]) -> None:
    atomic_write_json(
        {key: value for key, value in summary.items() if key != "holdings"},
        pointer_path,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ingest universe-scoped SEC 13F holdings.")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--universe", default=None, help="Path to universe.json; default broad-market feed.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.universe:
        uni = json.loads(Path(args.universe).read_text(encoding="utf-8"))
    else:
        uni = json.loads(Path(data_artifact_path("broad_market_paper_universe")).read_text(encoding="utf-8"))
    tickers = uni.get("tickers") if isinstance(uni, dict) else uni
    summary = ingest_universe_13f(universe=tickers or [], as_of=args.as_of, force=args.force)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
