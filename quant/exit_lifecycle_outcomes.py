"""Forward outcome ledger for exit-lifecycle shadow rows.

This module settles read-only production exit lifecycle observations into fixed
forward outcome rows. It does not rank candidates, size positions, alter exits,
or place orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Mapping, Sequence

from data_paths import DATA_ROOT


SCHEMA_VERSION = 1
OBSERVER_NAME = "exit_lifecycle"
SOURCE_RULE_VERSION = "exit_lifecycle_shadow_log_v1"
OUTCOME_RULE_VERSION = "exit_lifecycle_forward_outcome_ledger_v1"
DEFAULT_HORIZONS = (5,)
COMPARATORS = ("SPY", "QQQ")


def persist_exit_lifecycle_outcome_ledger(
    today: str | datetime | None = None,
    *,
    data_dir: str | Path | None = None,
    ohlcv_by_ticker: Mapping[str, Any] | None = None,
    warehouse_paths: Sequence[str | Path] | None = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
) -> dict[str, Any]:
    """Refresh the read-only exit lifecycle forward outcome ledger.

    The output is a daily full snapshot under
    ``data/exit_lifecycle/outcome_ledgers``. Source shadow rows remain the
    immutable observation surface; this ledger can be regenerated as OHLCV
    matures.
    """

    date_tag = _date_tag(today)
    paths = _artifact_paths(date_tag, data_dir)
    source_rows, source_files, skipped_rows = _load_source_rows_through(
        date_tag,
        data_dir=data_dir,
    )
    tickers = {
        str(row.get("ticker") or "").upper()
        for row in source_rows
        if str(row.get("ticker") or "").strip()
    }
    tickers.update(COMPARATORS)
    if ohlcv_by_ticker is None:
        bars, warehouse_summary = _load_warehouse_bars_for_tickers(
            tickers,
            data_dir=data_dir,
            warehouse_paths=warehouse_paths,
        )
    else:
        bars = {
            str(ticker).upper(): _ohlcv_rows(raw)
            for ticker, raw in ohlcv_by_ticker.items()
        }
        warehouse_summary = {
            "status": "provided",
            "requested_tickers": len(tickers),
            "returned_tickers": len([ticker for ticker, rows in bars.items() if rows]),
            "returned_rows": sum(len(rows) for rows in bars.values()),
            "sources": [],
        }

    normalized_horizons = tuple(sorted({int(horizon) for horizon in horizons}))
    outcome_rows = build_exit_lifecycle_outcome_ledger(
        source_rows,
        bars,
        as_of_date=date_tag,
        horizons=normalized_horizons,
    )
    summary = summarize_exit_lifecycle_outcomes(
        outcome_rows,
        source_rows=source_rows,
        source_files=source_files,
        skipped_source_rows=skipped_rows,
        as_of_date=date_tag,
        horizons=normalized_horizons,
        warehouse_summary=warehouse_summary,
        ledger_path=paths["outcome_ledger"],
        summary_path=paths["outcome_summary"],
        latest_summary_path=paths["latest_outcome_summary"],
    )
    write_exit_lifecycle_outcome_ledger(
        outcome_rows,
        summary,
        ledger_path=paths["outcome_ledger"],
        summary_path=paths["outcome_summary"],
        latest_summary_path=paths["latest_outcome_summary"],
    )
    return summary


def build_exit_lifecycle_outcome_ledger(
    source_rows: Sequence[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    as_of_date: str,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    spy_rows = list(ohlcv_by_ticker.get("SPY") or [])
    qqq_rows = list(ohlcv_by_ticker.get("QQQ") or [])
    for raw in source_rows:
        ticker = str(raw.get("ticker") or "").upper()
        observed_date = _date10(raw.get("as_of_date"))
        event_types = _event_types(raw)
        advisory_bucket, advisory_severity = _advisory_bucket(event_types, raw)
        observation_id = _observation_id(raw)
        base: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "exit_lifecycle_outcome",
            "observer_name": OBSERVER_NAME,
            "source_rule_version": raw.get("rule_version") or SOURCE_RULE_VERSION,
            "outcome_rule_version": OUTCOME_RULE_VERSION,
            "observation_id": observation_id,
            "ticker": ticker,
            "observed_date": observed_date,
            "as_of_date": as_of_date,
            "position_entry_date": _date10(raw.get("entry_date")),
            "target_price": _rounded(raw.get("target_price"), 4),
            "target_price_scope": "position_contract_not_fixed_horizon_exit",
            "shares": _rounded(raw.get("shares"), 6),
            "avg_cost": _rounded(raw.get("avg_cost"), 4),
            "market_value_usd": _rounded(raw.get("market_value_usd"), 2),
            "unrealized_pnl_pct": _rounded(raw.get("unrealized_pnl_pct"), 6),
            "daily_return_pct": _rounded(raw.get("daily_return_pct"), 6),
            "breach_status": raw.get("breach_status"),
            "drawdown_from_hwm_pct": _rounded(raw.get("drawdown_from_hwm_pct"), 6),
            "trailing_stop_from_hwm": _rounded(raw.get("trailing_stop_from_hwm"), 4),
            "has_advisory_event": bool(raw.get("has_advisory_event")),
            "event_types": event_types,
            "advisory_bucket": advisory_bucket,
            "advisory_severity": advisory_severity,
            "read_only": True,
            "alters_orders": False,
            "trade_enabled": False,
        }
        ticker_rows = list(ohlcv_by_ticker.get(ticker) or [])
        horizon_payloads = []
        for horizon in horizons:
            payload = _settle_horizon(
                observation_id=observation_id,
                ticker=ticker,
                observed_date=observed_date,
                ticker_rows=ticker_rows,
                spy_rows=spy_rows,
                qqq_rows=qqq_rows,
                notional_usd=_as_float(raw.get("market_value_usd")),
                horizon=int(horizon),
            )
            base.update(payload)
            horizon_payloads.append(payload)
        if horizon_payloads and all(
            payload.get(f"h{int(horizon)}_status") == "closed"
            for horizon, payload in zip(horizons, horizon_payloads)
        ):
            base["outcome_status"] = "closed"
        else:
            base["outcome_status"] = "pending_forward_close"
        rows.append(base)
    rows.sort(
        key=lambda row: (
            str(row.get("observed_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("observation_id") or ""),
        )
    )
    return rows


def summarize_exit_lifecycle_outcomes(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_rows: Sequence[Mapping[str, Any]],
    source_files: Sequence[str],
    skipped_source_rows: Sequence[Mapping[str, Any]],
    as_of_date: str,
    horizons: Sequence[int],
    warehouse_summary: Mapping[str, Any],
    ledger_path: str | Path,
    summary_path: str | Path,
    latest_summary_path: str | Path,
) -> dict[str, Any]:
    closed_by_horizon = {
        f"h{int(horizon)}": sum(
            1 for row in rows if row.get(f"h{int(horizon)}_status") == "closed"
        )
        for horizon in horizons
    }
    pending_by_horizon = {
        f"h{int(horizon)}": sum(
            1 for row in rows if row.get(f"h{int(horizon)}_status") != "closed"
        )
        for horizon in horizons
    }
    status_by_horizon = {
        f"h{int(horizon)}": dict(
            sorted(
                Counter(
                    str(row.get(f"h{int(horizon)}_status") or "missing")
                    for row in rows
                ).items()
            )
        )
        for horizon in horizons
    }
    closed_rows = [row for row in rows if row.get("outcome_status") == "closed"]
    return {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "outcome_rule_version": OUTCOME_RULE_VERSION,
        "status": "ok" if source_files else "missing_source_rows",
        "date": as_of_date,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source_file_count": len(source_files),
        "source_files": list(source_files),
        "source_row_count": len(source_rows),
        "skipped_source_rows": list(skipped_source_rows)[:50],
        "candidate_outcome_rows": len(rows),
        "settled_count": len(closed_rows),
        "unsettled_count": len(rows) - len(closed_rows),
        "horizons": [int(horizon) for horizon in horizons],
        "closed_rows_by_horizon": closed_by_horizon,
        "pending_rows_by_horizon": pending_by_horizon,
        "status_counts_by_horizon": status_by_horizon,
        "advisory_bucket_counts": dict(
            sorted(Counter(str(row.get("advisory_bucket") or "missing") for row in rows).items())
        ),
        "closed_advisory_bucket_counts": dict(
            sorted(
                Counter(
                    str(row.get("advisory_bucket") or "missing") for row in closed_rows
                ).items()
            )
        ),
        "replacement_value_by_horizon": _replacement_summary(rows, horizons),
        "warehouse": dict(warehouse_summary),
        "ledger_path": _path_text(ledger_path),
        "summary_path": _path_text(summary_path),
        "latest_summary_path": _path_text(latest_summary_path),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "scope": "exit_lifecycle_forward_outcome_settlement",
        },
    }


def write_exit_lifecycle_outcome_ledger(
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    *,
    ledger_path: str | Path,
    summary_path: str | Path,
    latest_summary_path: str | Path | None = None,
) -> None:
    ledger = Path(ledger_path)
    text = "".join(
        json.dumps(dict(row), ensure_ascii=False, default=str, sort_keys=True) + "\n"
        for row in rows
    )
    _write_text_direct(text, ledger)
    _write_json_direct(dict(summary), summary_path)
    if latest_summary_path is not None:
        _write_json_direct(dict(summary), latest_summary_path)


def _write_text_direct(text: str, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def _write_json_direct(payload: Mapping[str, Any], path: str | Path) -> None:
    _write_text_direct(
        json.dumps(dict(payload), ensure_ascii=False, default=str, indent=2) + "\n",
        path,
    )


def _artifact_paths(date_tag: str, data_dir: str | Path | None = None) -> dict[str, Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    base = root / OBSERVER_NAME
    return {
        "source_dir": base,
        "outcome_ledger": base
        / "outcome_ledgers"
        / f"{OBSERVER_NAME}_outcomes_{date_tag}.jsonl",
        "outcome_summary": base
        / "outcome_summaries"
        / f"{OBSERVER_NAME}_outcome_summary_{date_tag}.json",
        "latest_outcome_summary": base / "latest_outcome_summary.json",
    }


def _load_source_rows_through(
    date_tag: str,
    *,
    data_dir: str | Path | None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    paths = _artifact_paths(date_tag, data_dir)
    source_dir = paths["source_dir"]
    rows: list[dict[str, Any]] = []
    files: list[str] = []
    skipped: list[dict[str, Any]] = []
    if not source_dir.exists():
        return rows, files, skipped
    for path in sorted(source_dir.glob("exit_lifecycle_*.jsonl")):
        tag = path.stem.replace("exit_lifecycle_", "", 1)
        if tag > date_tag:
            continue
        files.append(_path_text(path))
        with path.open(encoding="utf-8-sig", errors="replace") as handle:
            for line_no, raw in enumerate(handle, start=1):
                text = raw.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    skipped.append(
                        {"file": _path_text(path), "line": line_no, "reason": "invalid_json"}
                    )
                    continue
                if not isinstance(row, dict):
                    skipped.append(
                        {"file": _path_text(path), "line": line_no, "reason": "not_object"}
                    )
                    continue
                ticker = str(row.get("ticker") or "").upper()
                observed_date = _date10(row.get("as_of_date"))
                market_value = _as_float(row.get("market_value_usd"))
                if not ticker or not observed_date or market_value is None or market_value <= 0:
                    skipped.append(
                        {
                            "file": _path_text(path),
                            "line": line_no,
                            "reason": "missing_required_fields",
                        }
                    )
                    continue
                rows.append({**row, "ticker": ticker, "as_of_date": observed_date})
    return rows, files, skipped


def _settle_horizon(
    *,
    observation_id: str,
    ticker: str,
    observed_date: str | None,
    ticker_rows: Sequence[Mapping[str, Any]],
    spy_rows: Sequence[Mapping[str, Any]],
    qqq_rows: Sequence[Mapping[str, Any]],
    notional_usd: float | None,
    horizon: int,
) -> dict[str, Any]:
    prefix = f"h{horizon}"
    empty = _empty_horizon(prefix, "missing_observed_date")
    if not observed_date:
        return empty
    if not ticker_rows:
        return _empty_horizon(prefix, "missing_ticker_bars")
    entry_index = _next_index_after(ticker_rows, observed_date)
    if entry_index is None:
        return _empty_horizon(prefix, "missing_next_session")
    exit_index = entry_index + horizon
    if exit_index >= len(ticker_rows):
        return _empty_horizon(prefix, "unsettled_horizon")
    entry_row = ticker_rows[entry_index]
    exit_row = ticker_rows[exit_index]
    entry_open = _as_float(entry_row.get("open"))
    exit_close = _as_float(exit_row.get("close"))
    entry_date = _date10(entry_row.get("date"))
    exit_date = _date10(exit_row.get("date"))
    if (
        entry_open is None
        or entry_open <= 0
        or exit_close is None
        or exit_close <= 0
        or not entry_date
        or not exit_date
        or notional_usd is None
        or notional_usd <= 0
    ):
        return _empty_horizon(prefix, "bad_price_or_notional")
    stock_return = exit_close / entry_open - 1.0
    pnl = notional_usd * stock_return
    spy_return = _return_between(spy_rows, entry_date, exit_date)
    qqq_return = _return_between(qqq_rows, entry_date, exit_date)
    spy_pnl = notional_usd * spy_return if spy_return is not None else None
    qqq_pnl = notional_usd * qqq_return if qqq_return is not None else None
    return {
        f"{prefix}_outcome_id": _hash(
            {
                "rule_version": OUTCOME_RULE_VERSION,
                "observation_id": observation_id,
                "horizon": horizon,
                "entry_date": entry_date,
                "exit_date": exit_date,
            }
        ),
        f"{prefix}_status": "closed",
        f"{prefix}_entry_date": entry_date,
        f"{prefix}_exit_date": exit_date,
        f"{prefix}_entry_open": round(entry_open, 4),
        f"{prefix}_exit_close": round(exit_close, 4),
        f"{prefix}_return_pct": round(stock_return, 8),
        f"{prefix}_pnl_usd": round(pnl, 2),
        f"{prefix}_spy_same_window_return_pct": round(spy_return, 8)
        if spy_return is not None
        else None,
        f"{prefix}_qqq_same_window_return_pct": round(qqq_return, 8)
        if qqq_return is not None
        else None,
        f"{prefix}_replacement_value_vs_cash_usd": round(pnl, 2),
        f"{prefix}_replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2)
        if spy_pnl is not None
        else None,
        f"{prefix}_replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2)
        if qqq_pnl is not None
        else None,
    }


def _empty_horizon(prefix: str, status: str) -> dict[str, Any]:
    return {
        f"{prefix}_outcome_id": None,
        f"{prefix}_status": status,
        f"{prefix}_entry_date": None,
        f"{prefix}_exit_date": None,
        f"{prefix}_entry_open": None,
        f"{prefix}_exit_close": None,
        f"{prefix}_return_pct": None,
        f"{prefix}_pnl_usd": None,
        f"{prefix}_spy_same_window_return_pct": None,
        f"{prefix}_qqq_same_window_return_pct": None,
        f"{prefix}_replacement_value_vs_cash_usd": None,
        f"{prefix}_replacement_value_vs_spy_usd": None,
        f"{prefix}_replacement_value_vs_qqq_usd": None,
    }


def _replacement_summary(
    rows: Sequence[Mapping[str, Any]],
    horizons: Sequence[int],
) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for horizon in horizons:
        prefix = f"h{int(horizon)}"
        out[prefix] = {
            "vs_cash": _summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_cash_usd") for row in rows]
            ),
            "vs_spy": _summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_spy_usd") for row in rows]
            ),
            "vs_qqq": _summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_qqq_usd") for row in rows]
            ),
        }
    return out


def _summarize_values(values: Iterable[Any]) -> dict[str, Any]:
    numeric = [value for value in (_as_float(item) for item in values) if value is not None]
    return {
        "count": len(numeric),
        "mean": round(mean(numeric), 4) if numeric else None,
        "median": round(median(numeric), 4) if numeric else None,
        "min": round(min(numeric), 4) if numeric else None,
        "max": round(max(numeric), 4) if numeric else None,
        "win_rate": round(sum(1 for value in numeric if value > 0) / len(numeric), 4)
        if numeric
        else None,
    }


def _load_warehouse_bars_for_tickers(
    tickers: set[str],
    *,
    data_dir: str | Path | None,
    warehouse_paths: Sequence[str | Path] | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = {str(ticker).upper() for ticker in tickers if str(ticker).strip()}
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    candidates = list(warehouse_paths or ())
    if not candidates:
        candidates = [
            root / "warehouse" / "warehouse_main_hot.sqlite",
            root / "warehouse" / "warehouse_main.sqlite",
        ]
    bars: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in requested}
    sources = []
    seen: set[tuple[str, str]] = set()
    for raw_path in candidates:
        path = Path(raw_path)
        if not path.is_absolute():
            path = root.parent / path if str(raw_path).startswith("data") else root / path
        source = {
            "path": _path_text(path),
            "exists": path.exists(),
            "returned_rows": 0,
            "status": "missing" if not path.exists() else "ok",
        }
        if path.exists() and requested:
            placeholders = ",".join("?" for _ in sorted(requested))
            query = (
                "select ticker, date, open, close from ohlcv "
                f"where ticker in ({placeholders}) order by ticker, date"
            )
            try:
                with sqlite3.connect(_sqlite_readonly_uri(path), uri=True) as con:
                    for ticker, day, open_, close in con.execute(query, sorted(requested)):
                        ticker_text = str(ticker).upper()
                        day_text = _date10(day)
                        if not day_text:
                            continue
                        key = (ticker_text, day_text)
                        if key in seen:
                            continue
                        seen.add(key)
                        bars.setdefault(ticker_text, []).append(
                            {
                                "date": day_text,
                                "open": _as_float(open_),
                                "close": _as_float(close),
                            }
                        )
                        source["returned_rows"] += 1
            except Exception as exc:
                source["status"] = "error"
                source["error"] = str(exc)
        sources.append(source)
    for ticker_rows in bars.values():
        ticker_rows.sort(key=lambda row: str(row.get("date") or ""))
    returned = sorted(ticker for ticker, ticker_rows in bars.items() if ticker_rows)
    all_dates = [
        str(row.get("date"))
        for ticker_rows in bars.values()
        for row in ticker_rows
        if row.get("date")
    ]
    return bars, {
        "status": "ok" if returned else "no_bars",
        "requested_tickers": len(requested),
        "returned_tickers": len(returned),
        "returned_rows": sum(len(ticker_rows) for ticker_rows in bars.values()),
        "date_min": min(all_dates) if all_dates else None,
        "date_max": max(all_dates) if all_dates else None,
        "sources": sources,
    }


def _ohlcv_rows(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if raw is None:
        return out
    if hasattr(raw, "iterrows"):
        for index, row in raw.iterrows():
            date_value = row.get("Date") if hasattr(row, "get") else None
            date_value = date_value if date_value is not None else index
            out.append(
                {
                    "date": _date10(date_value),
                    "open": _as_float(row.get("Open") if hasattr(row, "get") else None),
                    "close": _as_float(row.get("Close") if hasattr(row, "get") else None),
                }
            )
    elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            out.append(
                {
                    "date": _date10(item.get("date") or item.get("Date")),
                    "open": _as_float(item.get("open") or item.get("Open")),
                    "close": _as_float(item.get("close") or item.get("Close")),
                }
            )
    clean = [
        row
        for row in out
        if row.get("date") and row.get("open") is not None and row.get("close") is not None
    ]
    clean.sort(key=lambda row: str(row["date"]))
    return clean


def _event_types(row: Mapping[str, Any]) -> list[str]:
    return [
        str(event.get("event_type") or "")
        for event in row.get("advisory_events") or []
        if isinstance(event, Mapping)
    ]


def _advisory_bucket(
    event_types: Sequence[str],
    row: Mapping[str, Any],
) -> tuple[str, int]:
    if "hard_stop_breach" in event_types:
        return "hard_stop", 2
    if bool(row.get("has_advisory_event")) or "high_urgency_advisory" in event_types:
        return "high_urgency", 1
    return "none", 0


def _observation_id(row: Mapping[str, Any]) -> str:
    payload = {
        "rule_version": row.get("rule_version") or SOURCE_RULE_VERSION,
        "ticker": str(row.get("ticker") or "").upper(),
        "as_of_date": _date10(row.get("as_of_date")),
        "position_entry_date": _date10(row.get("entry_date")),
        "market_value_usd": _rounded(row.get("market_value_usd"), 2),
        "event_types": _event_types(row),
    }
    return _hash(payload)


def _return_between(
    rows: Sequence[Mapping[str, Any]],
    entry_date: str,
    exit_date: str,
) -> float | None:
    by_date = {str(row.get("date")): row for row in rows}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    entry_open = _as_float(entry.get("open"))
    exit_close = _as_float(exit_.get("close"))
    if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
        return None
    return exit_close / entry_open - 1.0


def _next_index_after(rows: Sequence[Mapping[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        row_day = _date10(row.get("date"))
        if row_day and row_day > day:
            return index
    return None


def _date_tag(today: str | datetime | None) -> str:
    if today is None:
        return datetime.now().strftime("%Y%m%d")
    if isinstance(today, datetime):
        return today.strftime("%Y%m%d")
    text = str(today)
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    return text.replace("-", "")[:8]


def _date10(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date().isoformat()
    except ValueError:
        if len(text) == 8 and text.isdigit():
            try:
                return datetime.strptime(text, "%Y%m%d").date().isoformat()
            except ValueError:
                return None
        return text[:10] if len(text) >= 10 else None


def _as_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _rounded(value: Any, digits: int = 6) -> float | None:
    number = _as_float(value)
    return round(number, digits) if number is not None else None


def _hash(payload: Mapping[str, Any], length: int = 24) -> str:
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def _sqlite_readonly_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/")


__all__ = [
    "OUTCOME_RULE_VERSION",
    "build_exit_lifecycle_outcome_ledger",
    "persist_exit_lifecycle_outcome_ledger",
    "summarize_exit_lifecycle_outcomes",
    "write_exit_lifecycle_outcome_ledger",
]
