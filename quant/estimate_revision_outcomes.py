"""Forward-only estimate revision outcome settlement helpers.

The outcome ledger attributes already-materialized estimate-revision rows to
fixed holding horizons. It does not rank candidates, size positions, alter
signals, or place paper/live orders.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Sequence

from constants import ROUND_TRIP_COST_PCT
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage


SCHEMA_VERSION = 1
DEFAULT_HORIZONS = (0, 1, 3, 5, 10)
COMPARATORS = ("SPY", "QQQ")
PROXY_NOTIONAL_USD = 4000.0


def persist_estimate_revision_outcomes(
    *,
    as_of: str | date,
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/non_ohlcv",
    ledger_path: str | Path | None = None,
    source_summary_path: str | Path | None = None,
    warehouse_path: str | Path | None = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    notional_usd: float = PROXY_NOTIONAL_USD,
    generated_at: datetime | None = None,
    run_adapter_changed: bool = True,
) -> dict[str, Any]:
    """Write the daily fixed-horizon estimate-revision outcome ledger.

    Rows are sourced from the post-quant estimate revision ledger for ``as_of``.
    Only rows that matched same-day candidates are settled; unmatched rows remain
    in the source ledger and are summarized as source coverage.
    """

    generated_at = generated_at or datetime.now(timezone.utc)
    as_of_date = _coerce_date(as_of)
    tag = as_of_date.strftime("%Y%m%d")
    output_root = Path(output_dir)
    source_ledger = Path(ledger_path) if ledger_path is not None else output_root / f"estimate_revision_ledger_{tag}.jsonl"
    source_summary = (
        Path(source_summary_path)
        if source_summary_path is not None
        else output_root / f"estimate_revision_ledger_summary_{tag}.json"
    )
    warehouse = (
        Path(warehouse_path)
        if warehouse_path is not None
        else Path(data_dir) / "warehouse" / "warehouse_main_hot.sqlite"
    )
    outcome_path = output_root / f"estimate_revision_outcomes_{tag}.jsonl"
    summary_path = output_root / f"estimate_revision_outcome_summary_{tag}.json"
    normalized_horizons = tuple(sorted({int(horizon) for horizon in horizons}))

    source_rows = _read_jsonl(source_ledger)
    source_summary_payload = _read_json(source_summary, default={})
    matched_rows = [
        row
        for row in source_rows
        if bool(row.get("matched_candidate_today") or row.get("matched_candidate_count"))
    ]
    matched_rows.sort(
        key=lambda row: (
            str(row.get("as_of_date") or as_of_date.isoformat()),
            str(row.get("ticker") or ""),
        )
    )

    warehouse_range = _warehouse_date_range(warehouse)
    latest_complete = warehouse_range.get("max_date")
    tickers = {
        str(row.get("ticker") or "").upper()
        for row in matched_rows
        if str(row.get("ticker") or "").strip()
    }
    tickers.update(COMPARATORS)
    bars = _load_bars(warehouse, tickers, as_of_date.isoformat(), latest_complete)

    outcome_rows = [
        _build_outcome_row(
            row=row,
            as_of_date=as_of_date,
            source_ledger=source_ledger,
            source_summary=source_summary,
            bars=bars,
            latest_complete=latest_complete,
            horizons=normalized_horizons,
            notional_usd=notional_usd,
        )
        for row in matched_rows
    ]
    summary = _summarize(
        as_of_date=as_of_date,
        generated_at=generated_at,
        data_dir=data_dir,
        source_rows=source_rows,
        source_summary_payload=source_summary_payload,
        source_ledger=source_ledger,
        source_summary=source_summary,
        outcome_rows=outcome_rows,
        warehouse=warehouse,
        warehouse_range=warehouse_range,
        bars=bars,
        horizons=normalized_horizons,
        notional_usd=notional_usd,
        output_path=outcome_path,
        summary_path=summary_path,
        run_adapter_changed=run_adapter_changed,
    )

    _write_jsonl(outcome_path, outcome_rows)
    _write_json(summary_path, summary)
    return summary


def persist_recent_estimate_revision_outcome_catchup(
    *,
    as_of: str | date,
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/non_ohlcv",
    warehouse_path: str | Path | None = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    notional_usd: float = PROXY_NOTIONAL_USD,
    generated_at: datetime | None = None,
    run_adapter_changed: bool = True,
    lookback_days: int = 10,
    exclude_dates: Sequence[str | date] = (),
    max_ledgers: int | None = None,
) -> dict[str, Any]:
    """Refresh recent estimate-revision outcome ledgers as OHLCV matures.

    Daily runs first create candidate-matched estimate-revision ledgers. Their
    forward outcomes may close later when the hot warehouse advances, so the
    settlement pipeline refreshes recent prior ledgers instead of requiring a
    new manual materialization ID for each day.
    """

    generated_at = generated_at or datetime.now(timezone.utc)
    as_of_date = _coerce_date(as_of)
    output_root = Path(output_dir)
    warehouse = (
        Path(warehouse_path)
        if warehouse_path is not None
        else Path(data_dir) / "warehouse" / "warehouse_main_hot.sqlite"
    )
    min_date = as_of_date - timedelta(days=max(int(lookback_days), 0))
    excluded = {_coerce_date(item).isoformat() for item in exclude_dates}
    candidates: list[tuple[date, Path]] = []
    for ledger_path in output_root.glob("estimate_revision_ledger_*.jsonl"):
        tag = ledger_path.stem.replace("estimate_revision_ledger_", "", 1)
        try:
            ledger_date = datetime.strptime(tag, "%Y%m%d").date()
        except ValueError:
            continue
        if ledger_date > as_of_date or ledger_date < min_date:
            continue
        if ledger_date.isoformat() in excluded:
            continue
        candidates.append((ledger_date, ledger_path))

    candidates.sort(key=lambda item: item[0], reverse=True)
    if max_ledgers is not None:
        candidates = candidates[: max(int(max_ledgers), 0)]

    summaries: list[dict[str, Any]] = []
    for ledger_date, ledger_path in candidates:
        tag = ledger_date.strftime("%Y%m%d")
        summaries.append(
            persist_estimate_revision_outcomes(
                as_of=ledger_date,
                data_dir=data_dir,
                output_dir=output_root,
                ledger_path=ledger_path,
                source_summary_path=output_root / f"estimate_revision_ledger_summary_{tag}.json",
                warehouse_path=warehouse,
                horizons=horizons,
                notional_usd=notional_usd,
                generated_at=generated_at,
                run_adapter_changed=run_adapter_changed,
            )
        )

    closed_counts: Counter[str] = Counter()
    pending_counts: Counter[str] = Counter()
    comparator_counts: Counter[str] = Counter()
    for summary in summaries:
        closed_counts.update(
            {
                str(key): int(value or 0)
                for key, value in (summary.get("closed_rows_by_horizon") or {}).items()
            }
        )
        pending_counts.update(
            {
                str(key): int(value or 0)
                for key, value in (summary.get("pending_rows_by_horizon") or {}).items()
            }
        )
        comparator_counts.update(
            {
                str(key): int(value or 0)
                for key, value in (
                    summary.get("comparator_complete_rows_by_horizon") or {}
                ).items()
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if summaries else "no_recent_ledgers",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "as_of_date": as_of_date.isoformat(),
        "data_dir": _path_text(data_dir),
        "output_dir": _path_text(output_root),
        "warehouse_path": _path_text(warehouse),
        "lookback_days": int(lookback_days),
        "excluded_dates": sorted(excluded),
        "refreshed_ledger_count": len(summaries),
        "refreshed_ledger_dates": [summary.get("as_of_date") for summary in summaries],
        "closed_rows_by_horizon": dict(sorted(closed_counts.items())),
        "pending_rows_by_horizon": dict(sorted(pending_counts.items())),
        "comparator_complete_rows_by_horizon": dict(sorted(comparator_counts.items())),
        "summaries": summaries,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": bool(run_adapter_changed),
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "default_off_forward_estimate_revision_outcome_catchup",
        },
    }


def _build_outcome_row(
    *,
    row: dict[str, Any],
    as_of_date: date,
    source_ledger: Path,
    source_summary: Path,
    bars: dict[str, list[dict[str, Any]]],
    latest_complete: str | None,
    horizons: Sequence[int],
    notional_usd: float,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    entry_date = _entry_date(row, as_of_date)
    direction = row.get("revision_direction_prev") or row.get("revision_direction")
    return {
        "schema_version": SCHEMA_VERSION,
        "source_revision_ledger": _path_text(source_ledger),
        "source_revision_summary": _path_text(source_summary),
        "ticker": ticker,
        "as_of_date": str(row.get("as_of_date") or as_of_date.isoformat()),
        "usable_entry_date": entry_date,
        "target_price": None,
        "target_price_scope": "not_applicable_fixed_horizon_replacement_value",
        "revision_direction": direction,
        "estimate_revision_usable": bool(row.get("estimate_revision_usable")),
        "matched_candidate_today": bool(
            row.get("matched_candidate_today") or row.get("matched_candidate_count")
        ),
        "matched_selected_signal_today": bool(
            row.get("matched_selected_signal_today") or row.get("matched_selected_signal_count")
        ),
        "matched_candidate_count": row.get("matched_candidate_count"),
        "matched_selected_signal_count": row.get("matched_selected_signal_count"),
        "matched_signal_sources": row.get("matched_signal_sources"),
        "matched_signal_record_types": row.get("matched_signal_record_types"),
        "matched_signal_strategies": row.get("matched_signal_strategies"),
        "matched_signal_records": row.get("matched_signal_records"),
        "eps_estimate": row.get("eps_estimate"),
        "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
        "next_earnings_date": row.get("next_earnings_date"),
        "source_snapshot_timestamp": row.get("source_snapshot_timestamp"),
        "source_snapshot_pit_safe": row.get("source_snapshot_pit_safe"),
        "paper_notional_usd": float(notional_usd),
        **_settle_horizons(
            ticker=ticker,
            requested_entry_date=entry_date,
            bars=bars,
            latest_complete=latest_complete,
            horizons=horizons,
            notional_usd=notional_usd,
        ),
    }


def _settle_horizons(
    *,
    ticker: str,
    requested_entry_date: str,
    bars: dict[str, list[dict[str, Any]]],
    latest_complete: str | None,
    horizons: Sequence[int],
    notional_usd: float,
) -> dict[str, Any]:
    ticker_rows = bars.get(ticker, [])
    entry_index = _first_index_on_or_after(ticker_rows, requested_entry_date)
    actual_entry_date: str | None = None
    if entry_index is not None:
        actual_entry_date = str(ticker_rows[entry_index].get("date"))

    result: dict[str, Any] = {
        "requested_entry_date": requested_entry_date,
        "entry_date": actual_entry_date or requested_entry_date,
        "actual_entry_date": actual_entry_date,
    }
    for horizon in horizons:
        prefix = f"h{horizon}"
        if entry_index is None or actual_entry_date is None:
            result.update(_empty_horizon(prefix, "missing_entry_bar"))
            continue

        exit_index = entry_index + int(horizon)
        if exit_index >= len(ticker_rows):
            result.update(_empty_horizon(prefix, "pending_forward_close"))
            continue

        exit_row = ticker_rows[exit_index]
        exit_date = str(exit_row.get("date"))
        if latest_complete is None or exit_date > latest_complete:
            result.update(_empty_horizon(prefix, "pending_forward_close"))
            continue

        pnl = _pnl_between_bars(ticker_rows[entry_index], exit_row, notional_usd)
        status = "closed" if pnl is not None else "bad_price"
        spy_pnl = _pnl_for_dates(
            bars.get("SPY", []),
            actual_entry_date,
            exit_date if pnl is not None else None,
            notional_usd,
        )
        qqq_pnl = _pnl_for_dates(
            bars.get("QQQ", []),
            actual_entry_date,
            exit_date if pnl is not None else None,
            notional_usd,
        )
        result.update(
            {
                f"{prefix}_status": status,
                f"{prefix}_exit_date": exit_date if pnl is not None else None,
                f"{prefix}_return_pct": round(pnl / notional_usd, 6)
                if pnl is not None and notional_usd
                else None,
                f"{prefix}_pnl_usd": round(pnl, 2) if pnl is not None else None,
                f"{prefix}_replacement_value_vs_cash_usd": round(pnl, 2)
                if pnl is not None
                else None,
                f"{prefix}_replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2)
                if pnl is not None and spy_pnl is not None
                else None,
                f"{prefix}_replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2)
                if pnl is not None and qqq_pnl is not None
                else None,
                f"{prefix}_spy_same_window_pnl_usd": round(spy_pnl, 2)
                if spy_pnl is not None
                else None,
                f"{prefix}_qqq_same_window_pnl_usd": round(qqq_pnl, 2)
                if qqq_pnl is not None
                else None,
            }
        )
    return result


def _summarize(
    *,
    as_of_date: date,
    generated_at: datetime,
    data_dir: str | Path,
    source_rows: list[dict[str, Any]],
    source_summary_payload: dict[str, Any],
    source_ledger: Path,
    source_summary: Path,
    outcome_rows: list[dict[str, Any]],
    warehouse: Path,
    warehouse_range: dict[str, Any],
    bars: dict[str, list[dict[str, Any]]],
    horizons: Sequence[int],
    notional_usd: float,
    output_path: Path,
    summary_path: Path,
    run_adapter_changed: bool,
) -> dict[str, Any]:
    matched_tickers = sorted({row["ticker"] for row in outcome_rows if row.get("ticker")})
    missing_tickers = sorted(ticker for ticker in matched_tickers if not bars.get(ticker))
    source_status = "ok"
    if not source_ledger.exists():
        source_status = "missing_source_ledger"
    elif not warehouse.exists():
        source_status = "missing_warehouse"
    elif not outcome_rows:
        source_status = "no_matched_candidate_rows"

    closed_counts = {
        f"h{horizon}": sum(1 for row in outcome_rows if row.get(f"h{horizon}_status") == "closed")
        for horizon in horizons
    }
    pending_counts = {
        f"h{horizon}": sum(
            1 for row in outcome_rows if row.get(f"h{horizon}_status") == "pending_forward_close"
        )
        for horizon in horizons
    }
    comparator_complete = {
        f"h{horizon}": sum(
            1
            for row in outcome_rows
            if row.get(f"h{horizon}_status") == "closed"
            and row.get(f"h{horizon}_replacement_value_vs_spy_usd") is not None
            and row.get(f"h{horizon}_replacement_value_vs_qqq_usd") is not None
        )
        for horizon in horizons
    }
    status_counts = {
        f"h{horizon}": dict(
            sorted(
                Counter(str(row.get(f"h{horizon}_status") or "missing") for row in outcome_rows).items()
            )
        )
        for horizon in horizons
    }
    direction_counts = Counter(
        str(row.get("revision_direction") or "missing") for row in outcome_rows
    )
    nonflat_usable = [
        row
        for row in outcome_rows
        if row.get("estimate_revision_usable")
        and str(row.get("revision_direction") or "").lower() not in {"", "flat", "missing"}
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": source_status,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "as_of_date": as_of_date.isoformat(),
        "data_dir": _path_text(data_dir),
        "source_revision_ledger": _path_text(source_ledger),
        "source_revision_ledger_exists": source_ledger.exists(),
        "source_revision_summary": _path_text(source_summary),
        "source_revision_summary_exists": source_summary.exists(),
        "source_revision_summary_payload": source_summary_payload,
        "warehouse_path": _path_text(warehouse),
        "warehouse_exists": warehouse.exists(),
        "warehouse_date_range": warehouse_range,
        "warehouse_loaded_tickers": sorted(ticker for ticker, rows in bars.items() if rows),
        "warehouse_missing_matched_tickers": missing_tickers,
        "output_path": _path_text(output_path),
        "summary_path": _path_text(summary_path),
        "horizons": list(horizons),
        "proxy_notional_usd": float(notional_usd),
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "slippage_bps_target": SLIPPAGE_BPS_TARGET,
        "source_ledger_row_count": len(source_rows),
        "matched_candidate_rows": len(outcome_rows),
        "matched_candidate_tickers": matched_tickers,
        "usable_matched_candidate_rows": sum(
            1 for row in outcome_rows if row.get("estimate_revision_usable")
        ),
        "nonflat_usable_matched_candidate_rows": len(nonflat_usable),
        "direction_counts": dict(sorted(direction_counts.items())),
        "closed_rows_by_horizon": closed_counts,
        "pending_rows_by_horizon": pending_counts,
        "comparator_complete_rows_by_horizon": comparator_complete,
        "status_counts_by_horizon": status_counts,
        "replacement_value_by_horizon": _replacement_summary(outcome_rows, horizons),
        "sample_rows": outcome_rows[:5],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": bool(run_adapter_changed),
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "default_off_forward_estimate_revision_outcome_settlement",
        },
    }


def _replacement_summary(
    rows: list[dict[str, Any]],
    horizons: Sequence[int],
) -> dict[str, dict[str, dict[str, Any]]]:
    summary: dict[str, dict[str, dict[str, Any]]] = {}
    for horizon in horizons:
        prefix = f"h{horizon}"
        summary[prefix] = {
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
    return summary


def _summarize_values(values: list[Any]) -> dict[str, Any]:
    numeric = [number for number in (_safe_float(value) for value in values) if number is not None]
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


def _empty_horizon(prefix: str, status: str) -> dict[str, Any]:
    return {
        f"{prefix}_status": status,
        f"{prefix}_exit_date": None,
        f"{prefix}_return_pct": None,
        f"{prefix}_pnl_usd": None,
        f"{prefix}_replacement_value_vs_cash_usd": None,
        f"{prefix}_replacement_value_vs_spy_usd": None,
        f"{prefix}_replacement_value_vs_qqq_usd": None,
        f"{prefix}_spy_same_window_pnl_usd": None,
        f"{prefix}_qqq_same_window_pnl_usd": None,
    }


def _load_bars(
    warehouse: Path,
    tickers: set[str],
    start: str,
    end: str | None,
) -> dict[str, list[dict[str, Any]]]:
    if not warehouse.exists() or not tickers or end is None:
        return {}
    placeholders = ",".join("?" for _ in sorted(tickers))
    query = (
        "select ticker, date, open, close from ohlcv "
        f"where ticker in ({placeholders}) and date >= ? and date <= ? "
        "order by ticker, date"
    )
    params = [*sorted(tickers), start, end]
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with sqlite3.connect(_sqlite_readonly_uri(warehouse), uri=True) as con:
        for ticker, day, open_, close in con.execute(query, params):
            rows_by_ticker[str(ticker).upper()].append(
                {
                    "date": str(day),
                    "open": _safe_float(open_),
                    "close": _safe_float(close),
                }
            )
    return dict(rows_by_ticker)


def _warehouse_date_range(warehouse: Path) -> dict[str, Any]:
    if not warehouse.exists():
        return {"min_date": None, "max_date": None, "rows": 0}
    with sqlite3.connect(_sqlite_readonly_uri(warehouse), uri=True) as con:
        min_date, max_date, rows = con.execute(
            "select min(date), max(date), count(*) from ohlcv"
        ).fetchone()
    return {"min_date": min_date, "max_date": max_date, "rows": int(rows or 0)}


def _pnl_for_dates(
    rows: list[dict[str, Any]],
    entry_date: str | None,
    exit_date: str | None,
    notional_usd: float,
) -> float | None:
    if not entry_date or not exit_date:
        return None
    by_date = {str(row.get("date")): row for row in rows}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    return _pnl_between_bars(entry, exit_, notional_usd)


def _pnl_between_bars(
    entry: dict[str, Any],
    exit_: dict[str, Any],
    notional_usd: float,
) -> float | None:
    entry_open = _safe_float(entry.get("open"))
    exit_close = _safe_float(exit_.get("close"))
    if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
        return None
    entry_price = apply_entry_fill(entry_open)
    exit_price = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
    return float(notional_usd) * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)


def _first_index_on_or_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if str(row.get("date")) >= day:
            return index
    return None


def _entry_date(row: dict[str, Any], fallback: date) -> str:
    raw = row.get("entry_date") or row.get("as_of_date") or fallback.isoformat()
    return _coerce_date(raw).isoformat()


def _coerce_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _safe_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _read_json(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default
    return payload if isinstance(payload, dict) else default


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sqlite_readonly_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/")
