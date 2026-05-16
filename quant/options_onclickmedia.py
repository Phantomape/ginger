"""Default-off OnclickMedia EOD options data adapter.

The adapter is intentionally data-only. It writes normalized option-chain rows
for later audit/shadow overlays and does not participate in signal generation,
ranking, sizing, or order construction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "non_ohlcv"
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "options" / "onclickmedia"
BASE_URL = "https://api.onclickmedia.com/options/"
SOURCE_NAME = "onclickmedia_options"
DEFAULT_USER_AGENT = "ginger-research/1.0 contact: research@example.com"
DEFAULT_MAX_EXPIRATIONS = 2
DEFAULT_MAX_STRIKES_PER_SIDE = 12
DEFAULT_REQUEST_SLEEP_SECONDS = 0.05
CALL_PUT_VALUES = ("call", "put")

FetchJson = Callable[..., Any]


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return REPO_ROOT / value


def _repo_rel(path: str | Path) -> str:
    value = _repo_path(path)
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _next_weekday(value: date) -> date:
    current = value
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current


def conservative_options_usable_trade_date(quote_date: date) -> str:
    """Treat EOD option rows as usable no earlier than the next weekday."""

    return _next_weekday(quote_date + timedelta(days=1)).isoformat()


def normalize_ticker(ticker: Any) -> str:
    return str(ticker or "").strip().upper().replace(".", "-")


def _float_value(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_value(value: Any) -> int | None:
    number = _float_value(value)
    if number is None:
        return None
    return int(number)


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]], *, append: bool = False) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with target.open(mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n")


def _cache_path(url: str, cache_dir: str | Path) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return _repo_path(cache_dir) / f"{digest}.json"


def fetch_onclickmedia_json(
    *,
    params: dict[str, Any],
    base_url: str = BASE_URL,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    timeout: float = 30.0,
    sleep_seconds: float = DEFAULT_REQUEST_SLEEP_SECONDS,
    user_agent: str = DEFAULT_USER_AGENT,
) -> Any:
    """Fetch JSON from OnclickMedia with a raw-response cache."""

    query_params = dict(params)
    query_params.setdefault("output", "json-v1")
    url = f"{base_url}?{urllib.parse.urlencode(query_params)}"
    cache_file = _cache_path(url, cache_dir)
    if cache_file.exists() and not refresh:
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        return cached.get("payload")

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec - research adapter URL is fixed.
        text = response.read().decode("utf-8")
    payload = json.loads(text)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(
            {
                "source": SOURCE_NAME,
                "url": url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return payload


def _first_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return value
    return []


def fetch_expirations(
    ticker: str,
    quote_date: date,
    *,
    call_put: str = "call",
    fetch_json: FetchJson = fetch_onclickmedia_json,
    **fetch_kwargs: Any,
) -> list[str]:
    payload = fetch_json(
        params={
            "ticker": normalize_ticker(ticker),
            "date": quote_date.isoformat(),
            "type": call_put,
            "list": "expiration",
        },
        **fetch_kwargs,
    )
    expirations = []
    for value in _first_list(payload):
        try:
            expirations.append(_parse_date(value).isoformat())
        except ValueError:
            continue
    return sorted(set(expirations))


def select_expirations(
    expirations: list[str],
    quote_date: date,
    *,
    max_expirations: int | None = DEFAULT_MAX_EXPIRATIONS,
) -> list[str]:
    parsed: list[date] = []
    for value in expirations:
        try:
            expiry = _parse_date(value)
        except ValueError:
            continue
        if expiry >= quote_date:
            parsed.append(expiry)
    parsed = sorted(set(parsed))
    if max_expirations is not None and max_expirations > 0:
        parsed = parsed[: int(max_expirations)]
    return [value.isoformat() for value in parsed]


def fetch_expiration_chain(
    ticker: str,
    quote_date: date,
    expiration: str,
    call_put: str,
    *,
    fetch_json: FetchJson = fetch_onclickmedia_json,
    **fetch_kwargs: Any,
) -> list[dict[str, Any]]:
    payload = fetch_json(
        params={
            "ticker": normalize_ticker(ticker),
            "date": quote_date.isoformat(),
            "expiration": expiration,
            "type": call_put,
            "data": "greeks",
        },
        **fetch_kwargs,
    )
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def option_liquidity_score(row: dict[str, Any]) -> float:
    bid = _float_value(row.get("bid"))
    ask = _float_value(row.get("ask"))
    mid = _float_value(row.get("mid") if row.get("mid") is not None else row.get("mark"))
    volume = _int_value(row.get("volume")) or 0
    open_interest = _int_value(row.get("open_interest")) or 0

    score = 0.0
    if bid is not None and ask is not None and bid > 0 and ask > bid:
        score += 0.25
    if bid is not None and ask is not None and mid and mid > 0 and ask >= bid:
        spread_pct = (ask - bid) / mid
        if spread_pct <= 0.10:
            score += 0.25
        elif spread_pct <= 0.25:
            score += 0.15
        elif spread_pct <= 0.50:
            score += 0.05
    if volume >= 100:
        score += 0.25
    elif volume >= 10:
        score += 0.15
    elif volume > 0:
        score += 0.05
    if open_interest >= 500:
        score += 0.25
    elif open_interest >= 100:
        score += 0.15
    elif open_interest > 0:
        score += 0.05
    return round(min(score, 1.0), 4)


def _strike_window_filter(
    rows: list[dict[str, Any]],
    *,
    underlying_price: float | None,
    max_strikes_per_side: int | None,
) -> list[dict[str, Any]]:
    if underlying_price is None or not max_strikes_per_side or max_strikes_per_side <= 0:
        return rows
    target_count = int(max_strikes_per_side) * 2 + 1
    return sorted(
        rows,
        key=lambda row: (
            abs((_float_value(row.get("strike")) or 0.0) - underlying_price),
            _float_value(row.get("strike")) or 0.0,
        ),
    )[:target_count]


def normalize_option_row(
    raw: dict[str, Any],
    *,
    ticker: str,
    quote_date: date,
    retrieved_at: str,
    collection_mode: str,
) -> dict[str, Any]:
    greeks = raw.get("greeks") if isinstance(raw.get("greeks"), dict) else {}
    bid = _float_value(raw.get("bid"))
    ask = _float_value(raw.get("ask"))
    mark = _float_value(raw.get("mark"))
    mid = mark
    if mid is None and bid is not None and ask is not None:
        mid = round((bid + ask) / 2.0, 6)

    normalized = {
        "source": SOURCE_NAME,
        "ticker": normalize_ticker(ticker),
        "date": quote_date.isoformat(),
        "quote_date": quote_date.isoformat(),
        "expiry": raw.get("expiration"),
        "expiration": raw.get("expiration"),
        "strike": _float_value(raw.get("strike")),
        "call_put": str(raw.get("type") or "").lower(),
        "last": _float_value(raw.get("last")),
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "mark": mark,
        "volume": _int_value(raw.get("volume")),
        "open_interest": _int_value(raw.get("open_interest")),
        "bid_size": _int_value(raw.get("bid_size")),
        "ask_size": _int_value(raw.get("ask_size")),
        "implied_vol": _float_value(greeks.get("implied_volatility")),
        "delta": _float_value(greeks.get("delta")),
        "gamma": _float_value(greeks.get("gamma")),
        "theta": _float_value(greeks.get("theta")),
        "vega": _float_value(greeks.get("vega")),
        "rho": _float_value(greeks.get("rho")),
        "usable_trade_date": conservative_options_usable_trade_date(quote_date),
        "retrieved_at": retrieved_at,
        "vendor_asof": None,
        "vendor_asof_available": False,
        "collection_mode": collection_mode,
        "source_url_base": BASE_URL,
    }
    normalized["option_liquidity_score"] = option_liquidity_score(normalized)
    normalized["option_liquidity_pass"] = normalized["option_liquidity_score"] >= 0.5

    if collection_mode == "forward_daily":
        normalized["pit_safe"] = True
        normalized["pit_safe_flag"] = "forward_collected_next_trade_day_usable"
        normalized["pit_caveat"] = (
            "Forward-collected from the free source and only usable from the next "
            "weekday; vendor_asof is unavailable and OI may have reporting lag."
        )
    else:
        normalized["pit_safe"] = False
        normalized["pit_safe_flag"] = "historical_backfill_vendor_asof_missing"
        normalized["pit_caveat"] = (
            "Historical backfill lacks vendor publication/as-of metadata; use for "
            "coverage/schema audits before treating as point-in-time evidence."
        )
    return normalized


def build_ticker_date_rows(
    *,
    ticker: str,
    quote_date: date,
    underlying_price: float | None = None,
    max_expirations: int | None = DEFAULT_MAX_EXPIRATIONS,
    max_strikes_per_side: int | None = DEFAULT_MAX_STRIKES_PER_SIDE,
    collection_mode: str = "historical_backfill",
    fetch_json: FetchJson = fetch_onclickmedia_json,
    fetch_kwargs: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fetch_kwargs = dict(fetch_kwargs or {})
    ticker_norm = normalize_ticker(ticker)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors: list[dict[str, Any]] = []
    requests_attempted = 0

    try:
        expiration_candidates = fetch_expirations(
            ticker_norm,
            quote_date,
            call_put="call",
            fetch_json=fetch_json,
            **fetch_kwargs,
        )
        requests_attempted += 1
    except Exception as exc:
        expiration_candidates = []
        errors.append({
            "ticker": ticker_norm,
            "date": quote_date.isoformat(),
            "stage": "expiration_list",
            "error": str(exc),
        })

    expirations = select_expirations(
        expiration_candidates,
        quote_date,
        max_expirations=max_expirations,
    )
    rows: list[dict[str, Any]] = []
    raw_rows_seen = 0
    raw_rows_after_strike_window = 0
    for expiration in expirations:
        for call_put in CALL_PUT_VALUES:
            try:
                raw_rows = fetch_expiration_chain(
                    ticker_norm,
                    quote_date,
                    expiration,
                    call_put,
                    fetch_json=fetch_json,
                    **fetch_kwargs,
                )
                requests_attempted += 1
            except Exception as exc:
                errors.append({
                    "ticker": ticker_norm,
                    "date": quote_date.isoformat(),
                    "expiration": expiration,
                    "call_put": call_put,
                    "stage": "chain",
                    "error": str(exc),
                })
                continue

            raw_rows_seen += len(raw_rows)
            raw_rows = _strike_window_filter(
                raw_rows,
                underlying_price=underlying_price,
                max_strikes_per_side=max_strikes_per_side,
            )
            raw_rows_after_strike_window += len(raw_rows)
            rows.extend(
                normalize_option_row(
                    raw,
                    ticker=ticker_norm,
                    quote_date=quote_date,
                    retrieved_at=retrieved_at,
                    collection_mode=collection_mode,
                )
                for raw in raw_rows
            )

    stats = {
        "ticker": ticker_norm,
        "date": quote_date.isoformat(),
        "underlying_price": underlying_price,
        "expiration_count": len(expirations),
        "expirations": expirations,
        "requests_attempted": requests_attempted,
        "raw_rows_seen": raw_rows_seen,
        "rows_after_strike_window": raw_rows_after_strike_window,
        "rows_written": len(rows),
        "errors": errors,
    }
    return rows, stats


def _iter_dates(start: date, end: date, *, include_weekends: bool = False) -> list[date]:
    out = []
    current = start
    while current <= end:
        if include_weekends or current.weekday() < 5:
            out.append(current)
        current += timedelta(days=1)
    return out


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _load_tickers_from_file(path: str | Path | None) -> list[str]:
    if not path:
        return []
    source = _repo_path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [normalize_ticker(item) for item in payload]
        if isinstance(payload, dict):
            values = payload.get("tickers") or payload.get("universe") or payload.get("data_universe")
            if isinstance(values, list):
                return [normalize_ticker(item) for item in values]
    return [
        normalize_ticker(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def run_options_backfill(
    *,
    tickers: list[str],
    start: date,
    end: date,
    output: str | Path,
    summary_output: str | Path,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    max_expirations: int | None = DEFAULT_MAX_EXPIRATIONS,
    max_strikes_per_side: int | None = DEFAULT_MAX_STRIKES_PER_SIDE,
    collection_mode: str = "historical_backfill",
    include_weekends: bool = False,
    sleep_seconds: float = DEFAULT_REQUEST_SLEEP_SECONDS,
    timeout: float = 30.0,
    underlying_prices: dict[str, float] | None = None,
    fetch_json: FetchJson = fetch_onclickmedia_json,
    append: bool = False,
) -> dict[str, Any]:
    tickers = sorted({normalize_ticker(ticker) for ticker in tickers if normalize_ticker(ticker)})
    dates = _iter_dates(start, end, include_weekends=include_weekends)
    rows: list[dict[str, Any]] = []
    per_ticker_date: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    fetch_kwargs = {
        "cache_dir": cache_dir,
        "refresh": refresh,
        "timeout": timeout,
        "sleep_seconds": sleep_seconds,
    }
    for quote_date in dates:
        for ticker in tickers:
            underlying_price = None
            if underlying_prices:
                underlying_price = underlying_prices.get(f"{ticker}|{quote_date.isoformat()}")
                if underlying_price is None:
                    underlying_price = underlying_prices.get(ticker)
            ticker_rows, stats = build_ticker_date_rows(
                ticker=ticker,
                quote_date=quote_date,
                underlying_price=underlying_price,
                max_expirations=max_expirations,
                max_strikes_per_side=max_strikes_per_side,
                collection_mode=collection_mode,
                fetch_json=fetch_json,
                fetch_kwargs=fetch_kwargs,
            )
            rows.extend(ticker_rows)
            per_ticker_date.append(stats)
            errors.extend(stats.get("errors", []))

    _write_jsonl(output, rows, append=append)
    by_ticker = Counter(row.get("ticker") for row in rows)
    by_date = Counter(row.get("date") for row in rows)
    liquidity_pass_count = sum(1 for row in rows if row.get("option_liquidity_pass"))
    pit_safe_count = sum(1 for row in rows if row.get("pit_safe"))
    summary = {
        "schema_version": 1,
        "source": SOURCE_NAME,
        "source_url_base": BASE_URL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "collection_mode": collection_mode,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "tickers_requested": tickers,
        "trading_dates_requested": [value.isoformat() for value in dates],
        "ticker_date_requests": len(tickers) * len(dates),
        "rows_written": len(rows),
        "pit_safe_rows": pit_safe_count,
        "pit_unsafe_rows": len(rows) - pit_safe_count,
        "option_liquidity_pass_rows": liquidity_pass_count,
        "option_liquidity_pass_rate": round(liquidity_pass_count / len(rows), 4) if rows else 0.0,
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_date": dict(sorted(by_date.items())),
        "errors": errors,
        "error_count": len(errors),
        "per_ticker_date": per_ticker_date,
        "parameters": {
            "max_expirations": max_expirations,
            "max_strikes_per_side": max_strikes_per_side,
            "include_weekends": include_weekends,
            "refresh": refresh,
            "append": append,
        },
        "output_path": _repo_rel(output),
        "summary_output": _repo_rel(summary_output),
        "pit_notes": [
            "Historical backfills lack vendor publication/as-of metadata and are marked pit_safe=false.",
            "Forward daily snapshots are usable no earlier than the next weekday.",
            "Open interest may have exchange/vendor lag and should not be used same-day.",
            "OnclickMedia is a free public-source aggregation feed; use coverage and quality audits before alpha claims.",
        ],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": collection_mode == "forward_daily",
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "options_data_collection_only",
        },
    }
    _write_json(summary_output, summary)
    return summary


def persist_daily_options_snapshot(
    *,
    as_of: str | date | datetime,
    tickers: list[str],
    underlying_prices: dict[str, float] | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    max_expirations: int | None = DEFAULT_MAX_EXPIRATIONS,
    max_strikes_per_side: int | None = DEFAULT_MAX_STRIKES_PER_SIDE,
    max_tickers: int | None = None,
    refresh: bool = False,
    sleep_seconds: float = DEFAULT_REQUEST_SLEEP_SECONDS,
    timeout: float = 30.0,
    logger: Any = None,
    fetch_json: FetchJson = fetch_onclickmedia_json,
) -> dict[str, Any]:
    as_of_date = _parse_date(as_of)
    tag = as_of_date.strftime("%Y%m%d")
    tickers_clean = sorted({normalize_ticker(ticker) for ticker in tickers if normalize_ticker(ticker)})
    if max_tickers is not None and max_tickers > 0:
        tickers_clean = tickers_clean[: int(max_tickers)]
    root = _repo_path(data_dir)
    output = root / f"options_onclickmedia_chain_{tag}.jsonl"
    summary_output = root / f"options_onclickmedia_summary_{tag}.json"

    summary = run_options_backfill(
        tickers=tickers_clean,
        start=as_of_date,
        end=as_of_date,
        output=output,
        summary_output=summary_output,
        cache_dir=DEFAULT_CACHE_DIR,
        refresh=refresh,
        max_expirations=max_expirations,
        max_strikes_per_side=max_strikes_per_side,
        collection_mode="forward_daily",
        include_weekends=True,
        sleep_seconds=sleep_seconds,
        timeout=timeout,
        underlying_prices=underlying_prices,
        fetch_json=fetch_json,
    )
    summary["status"] = "ok" if summary["rows_written"] > 0 or summary["error_count"] == 0 else "failed"
    if summary["rows_written"] > 0 and summary["error_count"] > 0:
        summary["status"] = "partial"
    _write_json(summary_output, summary)
    if logger:
        logger.info(
            "Daily OnclickMedia options snapshot: status=%s tickers=%s rows=%s errors=%s",
            summary["status"],
            len(tickers_clean),
            summary["rows_written"],
            summary["error_count"],
        )
    return summary


def _load_underlying_prices(path: str | None) -> dict[str, float]:
    if not path:
        return {}
    payload = json.loads(_repo_path(path).read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                for ticker, price in value.items():
                    parsed = _float_value(price)
                    if parsed is not None:
                        out[f"{normalize_ticker(ticker)}|{str(key)[:10]}"] = parsed
            else:
                parsed = _float_value(value)
                if parsed is not None:
                    out[normalize_ticker(key)] = parsed
    return out


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="Start quote date, YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="End quote date, YYYY-MM-DD.")
    parser.add_argument("--tickers", default="", help="Comma-separated ticker list.")
    parser.add_argument("--ticker-file", help="Text or JSON file containing tickers.")
    parser.add_argument("--output")
    parser.add_argument("--summary-output")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--max-expirations",
        type=int,
        default=DEFAULT_MAX_EXPIRATIONS,
        help="Nearest expirations per ticker/date. Use 0 for all expirations.",
    )
    parser.add_argument(
        "--max-strikes-per-side",
        type=int,
        default=DEFAULT_MAX_STRIKES_PER_SIDE,
        help="Keep N strikes on each side of underlying if prices are supplied. Use 0 for full chains.",
    )
    parser.add_argument("--full-chain", action="store_true", help="Fetch all expirations and all strikes.")
    parser.add_argument("--include-weekends", action="store_true")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_REQUEST_SLEEP_SECONDS)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--underlying-prices", help="Optional JSON mapping ticker or date->ticker to close price.")
    return parser


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    tickers = _parse_csv(args.tickers) + _load_tickers_from_file(args.ticker_file)
    if not tickers:
        raise SystemExit("Provide --tickers or --ticker-file")
    if end < start:
        raise SystemExit("--end must be >= --start")

    start_tag = start.strftime("%Y%m%d")
    end_tag = end.strftime("%Y%m%d")
    output = args.output or DEFAULT_DATA_DIR / f"options_onclickmedia_chain_{start_tag}_{end_tag}.jsonl"
    summary_output = (
        args.summary_output
        or DEFAULT_DATA_DIR / f"options_onclickmedia_summary_{start_tag}_{end_tag}.json"
    )
    max_expirations = None if args.full_chain or args.max_expirations == 0 else args.max_expirations
    max_strikes = 0 if args.full_chain else args.max_strikes_per_side
    summary = run_options_backfill(
        tickers=tickers,
        start=start,
        end=end,
        output=output,
        summary_output=summary_output,
        cache_dir=args.cache_dir,
        refresh=args.refresh,
        max_expirations=max_expirations,
        max_strikes_per_side=max_strikes,
        collection_mode="historical_backfill",
        include_weekends=args.include_weekends,
        sleep_seconds=args.sleep_seconds,
        timeout=args.timeout,
        underlying_prices=_load_underlying_prices(args.underlying_prices),
        append=args.append,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True, default=_json_default))
    return summary


if __name__ == "__main__":
    main()
