"""Default-off Kova data sidecars.

The sidecar turns Kova-inspired missing data surfaces into PIT-tagged rows that
experiments can join by `(ticker, asof_date)` without changing strategy logic.
Collectors are deliberately data-only: they do not create signals, orders,
ranking changes, sizing changes, or exits.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import os
import time
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from sec_companyfacts_backfill import (
        DEFAULT_CACHE_DIR as DEFAULT_COMPANYFACTS_CACHE_DIR,
        DEFAULT_USER_AGENT,
        backfill_companyfacts,
    )
except ImportError:  # pragma: no cover
    from quant.sec_companyfacts_backfill import (
        DEFAULT_CACHE_DIR as DEFAULT_COMPANYFACTS_CACHE_DIR,
        DEFAULT_USER_AGENT,
        backfill_companyfacts,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "kova"
DEFAULT_NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
DEFAULT_ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
DEFAULT_SEC13F_URL_TEMPLATE = (
    "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
    "{year}q{quarter}_form13f.zip"
)
DEFAULT_INTERVALS = ("15min", "60min")
INTRADAY_TIME_SERIES_PREFIX = "Time Series ("
FUNDAMENTAL_CANONICALS = {"revenue", "eps_diluted", "eps_basic", "net_income"}


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt, size in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%d", 10),
    ):
        try:
            return datetime.strptime(text[:size], fmt)
        except ValueError:
            continue
    return None


def _date_text(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError(f"invalid date: {value!r}")
    return parsed.isoformat()


def _date_tag(value: str | date | datetime) -> str:
    return _date_text(value).replace("-", "")


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
            count += 1
    return count


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def normalize_tickers(tickers: Iterable[str] | None) -> list[str]:
    out = {
        str(ticker).strip().upper()
        for ticker in (tickers or [])
        if str(ticker).strip()
    }
    return sorted(out)


def _safe_key(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
        upper = key.upper()
        if upper in row and row[upper] not in (None, ""):
            return row[upper]
        lower = key.lower()
        if lower in row and row[lower] not in (None, ""):
            return row[lower]
    return None


def alpha_vantage_intraday_url(
    ticker: str,
    *,
    interval: str,
    api_key: str,
    month: str | None = None,
    outputsize: str = "full",
    adjusted: bool = True,
    base_url: str = DEFAULT_ALPHA_VANTAGE_URL,
) -> str:
    query = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": ticker.upper(),
        "interval": interval,
        "outputsize": outputsize,
        "adjusted": "true" if adjusted else "false",
        "apikey": api_key,
        "datatype": "json",
    }
    if month:
        query["month"] = month
    return base_url + "?" + urllib.parse.urlencode(query)


def fetch_alpha_vantage_intraday_payload(
    ticker: str,
    *,
    interval: str,
    api_key: str,
    month: str | None = None,
    cache_dir: Path | str | None = None,
    refresh: bool = False,
    sleep_seconds: float = 12.1,
) -> dict[str, Any]:
    if not api_key:
        raise ValueError("Alpha Vantage API key is required for intraday fetch")
    cache_root = Path(cache_dir or DEFAULT_DATA_DIR / "cache" / "alpha_vantage_intraday")
    suffix = f"_{month}" if month else ""
    cache_path = cache_root / interval / f"{ticker.upper()}{suffix}.json"
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    request = urllib.request.Request(
        alpha_vantage_intraday_url(ticker, interval=interval, api_key=api_key, month=month),
        headers={"User-Agent": "ginger-kova-data-sidecar/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return payload


def parse_alpha_vantage_intraday_payload(
    payload: dict[str, Any],
    *,
    ticker: str,
    interval: str,
    asof_date: str | date | datetime,
    provider_asof_utc: str | None = None,
) -> list[dict[str, Any]]:
    asof = _date_text(asof_date)
    series_key = next(
        (
            key
            for key in payload
            if str(key).startswith(INTRADAY_TIME_SERIES_PREFIX)
            and str(interval) in str(key)
        ),
        None,
    )
    if not series_key:
        status = "rate_limited_or_error" if any(key in payload for key in ("Note", "Information", "Error Message")) else "missing_time_series"
        return [
            {
                "schema_version": 1,
                "surface": "intraday_ohlcv",
                "ticker": ticker.upper(),
                "asof_date": asof,
                "interval": interval,
                "provider": "alpha_vantage",
                "status": status,
                "error_message": payload.get("Note") or payload.get("Information") or payload.get("Error Message"),
                "alters_orders": False,
            }
        ]
    rows: list[dict[str, Any]] = []
    for timestamp, values in (payload.get(series_key) or {}).items():
        ts = _parse_datetime(timestamp)
        if ts is None:
            continue
        if ts.date().isoformat() > asof:
            continue
        rows.append(
            {
                "schema_version": 1,
                "surface": "intraday_ohlcv",
                "ticker": ticker.upper(),
                "asof_date": asof,
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "interval": interval,
                "open": _float_or_none(_safe_key(values, "1. open", "open")),
                "high": _float_or_none(_safe_key(values, "2. high", "high")),
                "low": _float_or_none(_safe_key(values, "3. low", "low")),
                "close": _float_or_none(_safe_key(values, "4. close", "close")),
                "volume": _float_or_none(_safe_key(values, "5. volume", "volume")),
                "provider": "alpha_vantage",
                "provider_asof_utc": provider_asof_utc,
                "status": "ok",
                "known_at": "provider_response_time; row timestamp must be <= asof_date for replay",
                "alters_orders": False,
            }
        )
    return sorted(rows, key=lambda row: (row["ticker"], row.get("timestamp") or ""))


def _compact_date_token_to_iso(token: str) -> str | None:
    if len(token) != 8 or not token.isdigit():
        return None
    return f"{token[:4]}-{token[4:6]}-{token[6:8]}"


def _companyfacts_file_date_range(path: Path) -> tuple[str | None, str | None]:
    dates = [
        text
        for text in (_compact_date_token_to_iso(part) for part in path.stem.split("_"))
        if text
    ]
    if not dates:
        return None, None
    return min(dates), max(dates)


def selected_companyfacts_paths(
    non_ohlcv_dir: Path | str = DEFAULT_NON_OHLCV_DIR,
    *,
    min_filed: str | date | datetime | None = None,
    max_filed: str | date | datetime | None = None,
) -> list[Path]:
    root = Path(non_ohlcv_dir)
    min_text = _date_text(min_filed) if min_filed is not None else None
    max_text = _date_text(max_filed) if max_filed is not None else None
    paths: list[Path] = []
    for path in sorted(root.glob("sec_companyfacts_selected_*.jsonl")):
        start, end = _companyfacts_file_date_range(path)
        if min_text and end and end < min_text:
            continue
        if max_text and start and start > max_text:
            continue
        paths.append(path)
    return paths


def load_selected_companyfacts_rows(
    *,
    non_ohlcv_dir: Path | str = DEFAULT_NON_OHLCV_DIR,
    min_filed: str | date | datetime | None = None,
    max_filed: str | date | datetime | None = None,
    tickers: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    ticker_set = set(normalize_tickers(tickers))
    min_filed_text = _date_text(min_filed) if min_filed is not None else None
    max_filed_text = _date_text(max_filed) if max_filed is not None else None
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for path in selected_companyfacts_paths(non_ohlcv_dir, min_filed=min_filed, max_filed=max_filed):
        for row in _read_jsonl(path):
            ticker = str(row.get("ticker") or "").upper()
            filed = str(row.get("filed") or "")[:10]
            if ticker_set and ticker not in ticker_set:
                continue
            if min_filed_text and filed < min_filed_text:
                continue
            if max_filed_text and filed > max_filed_text:
                continue
            key = (
                ticker,
                row.get("canonical"),
                row.get("concept"),
                row.get("unit"),
                row.get("value"),
                row.get("start"),
                row.get("end"),
                filed,
                row.get("form"),
                row.get("accession_number"),
                row.get("duration_days"),
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def derive_companyfacts_growth_rows(
    fact_rows: Iterable[dict[str, Any]],
    *,
    asof_date: str | date | datetime,
    tickers: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    asof = _date_text(asof_date)
    ticker_set = set(normalize_tickers(tickers))
    usable: list[dict[str, Any]] = []
    for row in fact_rows:
        ticker = str(row.get("ticker") or "").upper()
        filed = str(row.get("filed") or "")[:10]
        canonical = str(row.get("canonical") or "")
        if ticker_set and ticker not in ticker_set:
            continue
        if not ticker or not filed or filed > asof or canonical not in FUNDAMENTAL_CANONICALS:
            continue
        value = _float_or_none(row.get("value"))
        if value is None:
            continue
        usable.append({**row, "ticker": ticker, "filed": filed, "value": value})

    by_key: dict[tuple[str, str, Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for row in usable:
        key = (
            row["ticker"],
            str(row.get("canonical") or ""),
            row.get("fp"),
            row.get("duration_days"),
        )
        by_key[key].append(row)
    for rows in by_key.values():
        rows.sort(key=lambda item: (str(item.get("fy") or ""), str(item.get("end") or ""), str(item.get("filed") or "")))

    out: list[dict[str, Any]] = []
    for key, rows in by_key.items():
        prior_by_fy: dict[int, dict[str, Any]] = {}
        for row in rows:
            fy_raw = row.get("fy")
            try:
                fy = int(fy_raw)
            except (TypeError, ValueError):
                fy = None
            prior = prior_by_fy.get(fy - 1) if fy is not None else None
            prior_value = _float_or_none(prior.get("value")) if prior else None
            current_value = _float_or_none(row.get("value"))
            growth = None
            if prior_value not in (None, 0.0) and current_value is not None:
                growth = current_value / prior_value - 1.0
            out.append(
                {
                    "schema_version": 1,
                    "surface": "sec_companyfacts_growth",
                    "ticker": key[0],
                    "asof_date": str(row.get("filed") or asof)[:10],
                    "query_asof_date": asof,
                    "cik": row.get("cik"),
                    "canonical": key[1],
                    "current_value": current_value,
                    "current_period_end": row.get("end"),
                    "current_filed": row.get("filed"),
                    "current_form": row.get("form"),
                    "current_fp": row.get("fp"),
                    "current_fy": row.get("fy"),
                    "prior_value": prior_value,
                    "prior_period_end": prior.get("end") if prior else None,
                    "prior_filed": prior.get("filed") if prior else None,
                    "yoy_growth": round(growth, 6) if growth is not None else None,
                    "growth_status": "ok" if growth is not None else "missing_prior_period",
                    "provider": "sec_companyfacts",
                    "known_at": "SEC companyfacts filed date; use only rows with asof_date <= signal_date",
                    "alters_orders": False,
                }
            )
            if fy is not None:
                prior_by_fy[fy] = row
    return sorted(out, key=lambda row: (row["ticker"], row["asof_date"], row["canonical"], str(row.get("current_period_end") or "")))


def _load_ohlcv_snapshot(path: Path | str) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "ohlcv" in payload and isinstance(payload["ohlcv"], dict):
        return payload["ohlcv"]
    return payload


def normalize_ohlcv_mapping(
    ohlcv_data: dict[str, Any] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Convert in-memory OHLCV mappings, including pandas DataFrames, to rows."""
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, value in (ohlcv_data or {}).items():
        ticker_u = str(ticker).upper()
        if value is None:
            continue
        if isinstance(value, list):
            out[ticker_u] = [dict(row) for row in value if isinstance(row, dict)]
            continue
        if hasattr(value, "empty") and getattr(value, "empty"):
            continue
        if hasattr(value, "reset_index") and hasattr(value, "to_dict"):
            frame = value
            try:
                if "Date" not in frame.columns:
                    frame = frame.reset_index()
            except Exception:
                frame = frame.reset_index()
            rows: list[dict[str, Any]] = []
            for raw in frame.to_dict("records"):
                row: dict[str, Any] = {}
                for key in ("Date", "Open", "High", "Low", "Close", "Volume"):
                    if key in raw:
                        val = raw[key]
                    elif key.lower() in raw:
                        val = raw[key.lower()]
                    else:
                        continue
                    if key == "Date":
                        if hasattr(val, "date"):
                            val = val.date().isoformat()
                        else:
                            val = str(val)[:10]
                    elif hasattr(val, "item"):
                        val = val.item()
                    row[key] = val
                if row.get("Date") and row.get("Close") is not None:
                    rows.append(row)
            out[ticker_u] = rows
    return out


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _row_close(row: dict[str, Any]) -> float | None:
    return _float_or_none(row.get("Close") if "Close" in row else row.get("close"))


def _window_return(rows: list[dict[str, Any]], window: int) -> float | None:
    if len(rows) <= window:
        return None
    close_now = _row_close(rows[-1])
    close_then = _row_close(rows[-1 - window])
    if close_now is None or close_then in (None, 0.0):
        return None
    return close_now / close_then - 1.0


def _percentile_rank(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: item[1])
    count = len(ordered)
    if count <= 1:
        return {ticker: 1.0 for ticker, _ in ordered}
    ranks: dict[str, float] = {}
    for idx, (ticker, _) in enumerate(ordered):
        ranks[ticker] = round(idx / (count - 1), 6)
    return ranks


def compute_rs_proxy_rows(
    ohlcv: dict[str, list[dict[str, Any]]],
    *,
    asof_date: str | date | datetime,
    benchmark: str = "SPY",
    windows: tuple[int, ...] = (20, 60, 120),
    tickers: Iterable[str] | None = None,
    source_snapshot: str | None = None,
) -> list[dict[str, Any]]:
    asof = _date_text(asof_date)
    ticker_set = set(normalize_tickers(tickers))
    benchmark_rows = sorted(
        [row for row in ohlcv.get(benchmark, []) if _row_date(row) <= asof],
        key=_row_date,
    )
    benchmark_returns = {window: _window_return(benchmark_rows, window) for window in windows}
    raw_by_window: dict[int, dict[str, float]] = {window: {} for window in windows}
    row_inputs: dict[str, dict[str, Any]] = {}
    for ticker, rows_raw in ohlcv.items():
        ticker_u = str(ticker).upper()
        if ticker_u == benchmark or (ticker_set and ticker_u not in ticker_set):
            continue
        rows = sorted([row for row in rows_raw if _row_date(row) <= asof], key=_row_date)
        if not rows:
            continue
        row_inputs[ticker_u] = {
            "ticker": ticker_u,
            "asof_price_date": _row_date(rows[-1]),
            "row_count": len(rows),
        }
        for window in windows:
            ret = _window_return(rows, window)
            bench_ret = benchmark_returns.get(window)
            if ret is not None and bench_ret is not None:
                raw_by_window[window][ticker_u] = ret - bench_ret
                row_inputs[ticker_u][f"ret_{window}d"] = round(ret, 6)
                row_inputs[ticker_u][f"{benchmark.lower()}_ret_{window}d"] = round(bench_ret, 6)
                row_inputs[ticker_u][f"excess_ret_{window}d_vs_{benchmark.lower()}"] = round(ret - bench_ret, 6)
    ranks_by_window = {window: _percentile_rank(values) for window, values in raw_by_window.items()}
    out: list[dict[str, Any]] = []
    for ticker, base in sorted(row_inputs.items()):
        row = {
            "schema_version": 1,
            "surface": "ginger_rs_proxy",
            "ticker": ticker,
            "asof_date": asof,
            "benchmark": benchmark,
            "source_snapshot": source_snapshot,
            "status": "ok",
            "known_at": "daily OHLCV rows with date <= asof_date",
            "alters_orders": False,
            **base,
        }
        available = 0
        for window in windows:
            rank = ranks_by_window[window].get(ticker)
            row[f"rs_proxy_rank_pct_{window}d"] = rank
            if rank is not None:
                available += 1
        row["available_window_count"] = available
        if available == 0:
            row["status"] = "insufficient_history"
        out.append(row)
    return out


def load_cusip_ticker_map(path: Path | str | None) -> dict[str, str]:
    if path is None:
        return {}
    map_path = Path(path)
    if not map_path.exists():
        return {}
    if map_path.suffix.lower() == ".json":
        payload = json.loads(map_path.read_text(encoding="utf-8"))
        return {
            str(key).upper().replace(" ", ""): str(value).upper()
            for key, value in payload.items()
            if key and value
        }
    out: dict[str, str] = {}
    with map_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cusip = str(_safe_key(row, "cusip") or "").upper().replace(" ", "")
            ticker = str(_safe_key(row, "ticker", "symbol") or "").upper()
            if cusip and ticker:
                out[cusip] = ticker
    return out


def _read_delimited_table(raw: bytes, name: str) -> list[dict[str, Any]]:
    text = raw.decode("utf-8-sig", errors="replace")
    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def parse_sec13f_zip(
    zip_path: Path | str,
    *,
    asof_date: str | date | datetime,
    cusip_ticker_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    asof = _date_text(asof_date)
    mapping = {key.upper().replace(" ", ""): value.upper() for key, value in (cusip_ticker_map or {}).items()}
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        info_name = next((name for name in names if name.upper().endswith("INFOTABLE.TSV") or name.upper().endswith("INFOTABLE.CSV")), None)
        sub_name = next((name for name in names if name.upper().endswith("SUBMISSION.TSV") or name.upper().endswith("SUBMISSION.CSV")), None)
        if not info_name:
            raise ValueError("SEC 13F zip missing INFOTABLE table")
        info_rows = _read_delimited_table(archive.read(info_name), info_name)
        submission_rows = _read_delimited_table(archive.read(sub_name), sub_name) if sub_name else []

    submissions = {
        str(_safe_key(row, "ACCESSION_NUMBER", "accession_number") or ""): row
        for row in submission_rows
    }
    rows: list[dict[str, Any]] = []
    for item in info_rows:
        accession = str(_safe_key(item, "ACCESSION_NUMBER", "accession_number") or "")
        submission = submissions.get(accession, {})
        filing_date = str(_safe_key(submission, "FILING_DATE", "filing_date") or _safe_key(item, "FILING_DATE", "filing_date") or "")[:10]
        if filing_date and filing_date > asof:
            continue
        cusip = str(_safe_key(item, "CUSIP", "cusip") or "").upper().replace(" ", "")
        ticker = mapping.get(cusip)
        rows.append(
            {
                "schema_version": 1,
                "surface": "sec13f_institutional_ownership",
                "ticker": ticker,
                "ticker_mapping_status": "cusip_map_exact" if ticker else "missing_cusip_ticker_map",
                "asof_date": filing_date or asof,
                "query_asof_date": asof,
                "accession_number": accession or None,
                "manager_name": _safe_key(submission, "FILINGMANAGER_NAME", "filingmanager_name", "manager_name"),
                "manager_cik": _safe_key(submission, "CIK", "cik", "manager_cik"),
                "report_period": _safe_key(submission, "PERIODOFREPORT", "periodofreport", "report_period"),
                "name_of_issuer": _safe_key(item, "NAMEOFISSUER", "nameofissuer", "name_of_issuer"),
                "title_of_class": _safe_key(item, "TITLEOFCLASS", "titleofclass", "title_of_class"),
                "cusip": cusip or None,
                "value_usd_thousands": _float_or_none(_safe_key(item, "VALUE", "value")),
                "shares": _float_or_none(_safe_key(item, "SSHPRNAMT", "sshprnamt", "shares")),
                "put_call": _safe_key(item, "PUTCALL", "putcall"),
                "investment_discretion": _safe_key(item, "INVESTMENTDISCRETION", "investmentdiscretion"),
                "provider": "sec_13f_data_set",
                "known_at": "SEC 13F filing date; ticker join requires separate CUSIP map",
                "alters_orders": False,
            }
        )
    return sorted(rows, key=lambda row: (str(row.get("ticker") or ""), str(row.get("asof_date") or ""), str(row.get("accession_number") or "")))


def fetch_sec13f_quarter_zip(
    year: int,
    quarter: int,
    *,
    cache_dir: Path | str | None = None,
    refresh: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
    url_template: str = DEFAULT_SEC13F_URL_TEMPLATE,
) -> Path:
    if quarter not in {1, 2, 3, 4}:
        raise ValueError("quarter must be 1-4")
    cache_root = Path(cache_dir or DEFAULT_DATA_DIR / "cache" / "sec13f")
    path = cache_root / f"{year}q{quarter}_form13f.zip"
    if path.exists() and not refresh:
        return path
    url = url_template.format(year=year, quarter=quarter)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _latest_rows_by_surface(
    rows: Iterable[dict[str, Any]],
    *,
    ticker: str,
    asof_date: str | date | datetime,
) -> dict[str, dict[str, Any]]:
    asof = _date_text(asof_date)
    ticker_u = ticker.upper()
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("ticker") or "").upper() != ticker_u:
            continue
        row_asof = str(row.get("asof_date") or "")[:10]
        if not row_asof or row_asof > asof:
            continue
        surface = str(row.get("surface") or "")
        current = latest.get(surface)
        if current is None or row_asof > str(current.get("asof_date") or "")[:10]:
            latest[surface] = row
    return latest


def load_kova_context(
    *,
    ticker: str,
    asof_date: str | date | datetime,
    data_dir: Path | str = DEFAULT_DATA_DIR,
) -> dict[str, Any]:
    root = Path(data_dir)
    rows: list[dict[str, Any]] = []
    for path in root.rglob("*.jsonl"):
        rows.extend(_read_jsonl(path))
    asof = _date_text(asof_date)
    ticker_u = ticker.upper()
    eligible = [
        row
        for row in rows
        if str(row.get("ticker") or "").upper() == ticker_u
        and str(row.get("asof_date") or "")[:10]
        and str(row.get("asof_date") or "")[:10] <= asof
    ]
    fundamentals: dict[str, dict[str, Any]] = {}
    for row in eligible:
        if row.get("surface") != "sec_companyfacts_growth":
            continue
        canonical = str(row.get("canonical") or "")
        if not canonical:
            continue
        current = fundamentals.get(canonical)
        row_key = (
            str(row.get("asof_date") or "")[:10],
            str(row.get("current_period_end") or ""),
        )
        current_key = (
            str(current.get("asof_date") or "")[:10],
            str(current.get("current_period_end") or ""),
        ) if current else ("", "")
        if current is None or row_key > current_key:
            fundamentals[canonical] = row
    return {
        "ticker": ticker_u,
        "asof_date": asof,
        "surfaces": _latest_rows_by_surface(rows, ticker=ticker, asof_date=asof_date),
        "fundamental_growth_by_canonical": fundamentals,
        "institutional_ownership_rows": [
            row
            for row in eligible
            if row.get("surface") == "sec13f_institutional_ownership"
            and row.get("status") != "skipped"
        ],
        "intraday_rows": [
            row
            for row in eligible
            if row.get("surface") == "intraday_ohlcv"
            and row.get("status") == "ok"
        ],
    }


def sidecar_paths(data_dir: Path | str, asof_date: str | date | datetime) -> dict[str, Path]:
    root = Path(data_dir)
    tag = _date_tag(asof_date)
    return {
        "intraday": root / "intraday" / f"intraday_ohlcv_{tag}.jsonl",
        "fundamental_growth": root / "fundamentals" / f"companyfacts_growth_{tag}.jsonl",
        "institutional_ownership": root / "institutional" / f"sec13f_ownership_{tag}.jsonl",
        "rs_proxy": root / "rs_proxy" / f"rs_proxy_{tag}.jsonl",
        "snapshot": root / "snapshots" / f"kova_data_snapshot_{tag}.json",
    }


def persist_kova_data_snapshot(
    *,
    asof_date: str | date | datetime,
    tickers: Iterable[str],
    data_dir: Path | str = DEFAULT_DATA_DIR,
    non_ohlcv_dir: Path | str = DEFAULT_NON_OHLCV_DIR,
    ohlcv_snapshot: Path | str | None = None,
    ohlcv_data: dict[str, Any] | None = None,
    alpha_vantage_api_key: str | None = None,
    refresh_intraday: bool = False,
    intervals: tuple[str, ...] = DEFAULT_INTERVALS,
    month: str | None = None,
    refresh_companyfacts: bool = False,
    companyfacts_max_ciks: int | None = None,
    companyfacts_lookback_days: int | None = 820,
    sec13f_zip: Path | str | None = None,
    sec13f_year: int | None = None,
    sec13f_quarter: int | None = None,
    cusip_map: Path | str | None = None,
    refresh_sec13f: bool = False,
    sleep_seconds: float = 0.11,
) -> dict[str, Any]:
    asof = _date_text(asof_date)
    ticker_list = normalize_tickers(tickers)
    paths = sidecar_paths(data_dir, asof)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": generated_at,
        "asof_date": asof,
        "tickers": ticker_list,
        "paths": {key: _repo_rel(path) for key, path in paths.items()},
        "status": "started",
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "scope": "kova_data_sidecar_refresh_only",
        },
    }

    intraday_rows: list[dict[str, Any]] = []
    if refresh_intraday and alpha_vantage_api_key:
        for ticker in ticker_list:
            for interval in intervals:
                try:
                    payload = fetch_alpha_vantage_intraday_payload(
                        ticker,
                        interval=interval,
                        api_key=alpha_vantage_api_key,
                        month=month,
                        sleep_seconds=sleep_seconds,
                    )
                    intraday_rows.extend(
                        parse_alpha_vantage_intraday_payload(
                            payload,
                            ticker=ticker,
                            interval=interval,
                            asof_date=asof,
                            provider_asof_utc=generated_at,
                        )
                    )
                except Exception as exc:  # pragma: no cover - live network path
                    intraday_rows.append(
                        {
                            "schema_version": 1,
                            "surface": "intraday_ohlcv",
                            "ticker": ticker,
                            "asof_date": asof,
                            "interval": interval,
                            "provider": "alpha_vantage",
                            "status": "failed",
                            "error_message": str(exc),
                            "alters_orders": False,
                        }
                    )
    else:
        intraday_rows = [
            {
                "schema_version": 1,
                "surface": "intraday_ohlcv",
                "ticker": ticker,
                "asof_date": asof,
                "provider": "alpha_vantage",
                "status": "skipped",
                "reason": "refresh_intraday_false_or_missing_ALPHA_VANTAGE_API_KEY",
                "alters_orders": False,
            }
            for ticker in ticker_list
        ]
    snapshot["intraday_ohlcv"] = {
        "status": "ok" if any(row.get("status") == "ok" for row in intraday_rows) else "skipped_or_failed",
        "rows_written": _write_jsonl(paths["intraday"], intraday_rows),
        "provider": "alpha_vantage",
        "requires_api_key": True,
    }

    companyfacts_summary = None
    if refresh_companyfacts:
        args = argparse.Namespace(
            start=asof,
            end=asof,
            output=str(Path(non_ohlcv_dir) / f"sec_companyfacts_selected_kova_{_date_tag(asof)}.jsonl"),
            summary_output=str(Path(non_ohlcv_dir) / f"sec_companyfacts_backfill_summary_kova_{_date_tag(asof)}.json"),
            cache_dir=str(DEFAULT_COMPANYFACTS_CACHE_DIR),
            segments=["core", "pilot", "observation"],
            tickers=ticker_list,
            max_ciks=companyfacts_max_ciks,
            include_etfs=False,
            refresh=False,
            forms=["8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A"],
            prior_period_days=550,
            user_agent=DEFAULT_USER_AGENT,
            sleep_seconds=sleep_seconds,
        )
        companyfacts_summary = backfill_companyfacts(args)
    min_companyfacts_filed = None
    if companyfacts_lookback_days is not None:
        asof_obj = _parse_date(asof)
        if asof_obj is not None:
            min_companyfacts_filed = asof_obj - timedelta(days=max(int(companyfacts_lookback_days), 0))
    fact_rows = load_selected_companyfacts_rows(
        non_ohlcv_dir=non_ohlcv_dir,
        min_filed=min_companyfacts_filed,
        max_filed=asof,
        tickers=ticker_list,
    )
    growth_rows = derive_companyfacts_growth_rows(fact_rows, asof_date=asof, tickers=ticker_list)
    snapshot["fundamental_growth"] = {
        "status": "ok" if growth_rows else "empty",
        "rows_written": _write_jsonl(paths["fundamental_growth"], growth_rows),
        "source_rows": len(fact_rows),
        "lookback_days": companyfacts_lookback_days,
        "companyfacts_backfill_summary": companyfacts_summary,
    }

    rs_rows: list[dict[str, Any]] = []
    if ohlcv_data is not None:
        ohlcv = normalize_ohlcv_mapping(ohlcv_data)
        rs_rows = compute_rs_proxy_rows(
            ohlcv,
            asof_date=asof,
            tickers=ticker_list,
            source_snapshot="in_memory_production_ohlcv",
        )
    elif ohlcv_snapshot:
        ohlcv = _load_ohlcv_snapshot(ohlcv_snapshot)
        rs_rows = compute_rs_proxy_rows(
            ohlcv,
            asof_date=asof,
            tickers=ticker_list,
            source_snapshot=_repo_rel(ohlcv_snapshot),
        )
    snapshot["rs_proxy"] = {
        "status": "ok" if rs_rows else "skipped_or_empty",
        "rows_written": _write_jsonl(paths["rs_proxy"], rs_rows),
        "source_snapshot": (
            "in_memory_production_ohlcv"
            if ohlcv_data is not None
            else (_repo_rel(ohlcv_snapshot) if ohlcv_snapshot else None)
        ),
    }

    sec13f_rows: list[dict[str, Any]] = []
    mapping = load_cusip_ticker_map(cusip_map)
    if sec13f_zip or (sec13f_year and sec13f_quarter):
        zip_path = (
            Path(sec13f_zip)
            if sec13f_zip
            else fetch_sec13f_quarter_zip(
                int(sec13f_year),
                int(sec13f_quarter),
                refresh=refresh_sec13f,
                user_agent=DEFAULT_USER_AGENT,
            )
        )
        sec13f_rows = parse_sec13f_zip(zip_path, asof_date=asof, cusip_ticker_map=mapping)
        ticker_filter = set(ticker_list)
        if ticker_filter:
            sec13f_rows = [
                row for row in sec13f_rows if not row.get("ticker") or row.get("ticker") in ticker_filter
            ]
    else:
        sec13f_rows = [
            {
                "schema_version": 1,
                "surface": "sec13f_institutional_ownership",
                "ticker": ticker,
                "asof_date": asof,
                "status": "skipped",
                "reason": "no_sec13f_zip_or_year_quarter_supplied",
                "provider": "sec_13f_data_set",
                "alters_orders": False,
            }
            for ticker in ticker_list
        ]
    snapshot["institutional_ownership"] = {
        "status": "ok" if any(row.get("surface") == "sec13f_institutional_ownership" and row.get("status") != "skipped" for row in sec13f_rows) else "skipped_or_empty",
        "rows_written": _write_jsonl(paths["institutional_ownership"], sec13f_rows),
        "cusip_map_rows": len(mapping),
    }

    statuses = [
        snapshot["intraday_ohlcv"]["status"],
        snapshot["fundamental_growth"]["status"],
        snapshot["rs_proxy"]["status"],
        snapshot["institutional_ownership"]["status"],
    ]
    snapshot["status"] = "ok" if any(status == "ok" for status in statuses) else "skipped_or_empty"
    _write_json(paths["snapshot"], snapshot)
    return snapshot


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh default-off Kova data sidecars.")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--tickers", nargs="*", default=None)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--non-ohlcv-dir", default=str(DEFAULT_NON_OHLCV_DIR))
    parser.add_argument("--ohlcv-snapshot", default=None)
    parser.add_argument("--alpha-vantage-api-key", default=os.environ.get("ALPHA_VANTAGE_API_KEY"))
    parser.add_argument("--refresh-intraday", action="store_true")
    parser.add_argument("--intervals", nargs="*", default=list(DEFAULT_INTERVALS))
    parser.add_argument("--month", default=None)
    parser.add_argument("--refresh-companyfacts", action="store_true")
    parser.add_argument("--companyfacts-max-ciks", type=int, default=None)
    parser.add_argument("--companyfacts-lookback-days", type=int, default=820)
    parser.add_argument("--sec13f-zip", default=None)
    parser.add_argument("--sec13f-year", type=int, default=None)
    parser.add_argument("--sec13f-quarter", type=int, default=None)
    parser.add_argument("--cusip-map", default=None)
    parser.add_argument("--refresh-sec13f", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.11)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    snapshot = persist_kova_data_snapshot(
        asof_date=args.as_of,
        tickers=args.tickers or [],
        data_dir=args.data_dir,
        non_ohlcv_dir=args.non_ohlcv_dir,
        ohlcv_snapshot=args.ohlcv_snapshot,
        alpha_vantage_api_key=args.alpha_vantage_api_key,
        refresh_intraday=args.refresh_intraday,
        intervals=tuple(args.intervals),
        month=args.month,
        refresh_companyfacts=args.refresh_companyfacts,
        companyfacts_max_ciks=args.companyfacts_max_ciks,
        companyfacts_lookback_days=args.companyfacts_lookback_days,
        sec13f_zip=args.sec13f_zip,
        sec13f_year=args.sec13f_year,
        sec13f_quarter=args.sec13f_quarter,
        cusip_map=args.cusip_map,
        refresh_sec13f=args.refresh_sec13f,
        sleep_seconds=args.sleep_seconds,
    )
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "asof_date": snapshot["asof_date"],
                "intraday_rows": snapshot["intraday_ohlcv"]["rows_written"],
                "fundamental_rows": snapshot["fundamental_growth"]["rows_written"],
                "rs_proxy_rows": snapshot["rs_proxy"]["rows_written"],
                "institutional_rows": snapshot["institutional_ownership"]["rows_written"],
                "snapshot": snapshot["paths"]["snapshot"],
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
