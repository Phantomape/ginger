"""Observer-only entity/theme news collection.

This module intentionally stays out of the trade-news prompt path.  It collects
RSS rows for non-listed entities and themes that can later be mapped to listed
exposure tickers, then writes separate observer artifacts for replay.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from data_paths import DATA_ROOT, atomic_write_json

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
OBSERVER_NAME = "entity_theme_news_observer"
ARTIFACT_ROOT = Path("non_ohlcv") / OBSERVER_NAME
OUTCOME_RULE_VERSION = "entity_theme_news_forward_outcome_ledger_v1"


ENTITY_THEME_SOURCE_SPECS = [
    {
        "query_id": "private_space_launch_contracts",
        "query": '"SpaceX" launch contract OR Starship OR Starlink',
        "primary_entity": "SpaceX",
        "theme": "private_space_contracts",
        "relation_type": "private_entity_to_public_space_exposure",
        "candidate_tickers": ["RKLB", "LUNR", "ASTS", "BA", "LMT", "NOC"],
        "rationale": (
            "Private space news can reprice public space, launch, satellite, "
            "and defense-prime exposure before ticker-scoped feeds see it."
        ),
    },
    {
        "query_id": "frontier_ai_private_capex",
        "query": '"OpenAI" OR Anthropic data center chips investment',
        "primary_entity": "frontier_ai_labs",
        "theme": "ai_capex_private_lab",
        "relation_type": "private_ai_lab_to_public_ai_infrastructure",
        "candidate_tickers": ["NVDA", "AMD", "AVGO", "MU", "CRDO", "ANET", "SMCI"],
        "rationale": (
            "Private AI lab capex and supply commitments can transmit to public "
            "AI infrastructure suppliers."
        ),
    },
    {
        "query_id": "ai_export_control_supply_chain",
        "query": '"AI chips" export controls China Nvidia AMD',
        "primary_entity": "US_export_control_policy",
        "theme": "ai_chip_export_controls",
        "relation_type": "regulatory_policy_to_public_semiconductor_exposure",
        "candidate_tickers": ["NVDA", "AMD", "AVGO", "TSM", "ASML", "MU"],
        "rationale": (
            "Regulatory headlines can affect semiconductor revenue paths before "
            "single-ticker feeds classify the event."
        ),
    },
    {
        "query_id": "hyperscaler_power_data_center",
        "query": 'data center power grid hyperscaler AI electricity',
        "primary_entity": "hyperscaler_power_demand",
        "theme": "ai_data_center_power",
        "relation_type": "theme_to_public_power_and_infrastructure_exposure",
        "candidate_tickers": ["CEG", "VST", "ETN", "PWR", "GEV", "NVDA", "ANET"],
        "rationale": (
            "Power and infrastructure bottlenecks can redirect AI capex and "
            "benefit public grid, equipment, and compute suppliers."
        ),
    },
    {
        "query_id": "glp1_supply_access",
        "query": 'GLP-1 obesity drug supply Medicare compounding FDA',
        "primary_entity": "GLP1_market_access",
        "theme": "glp1_supply_access",
        "relation_type": "healthcare_theme_to_public_obesity_drug_exposure",
        "candidate_tickers": ["LLY", "NVO", "HIMS", "WW"],
        "rationale": (
            "Policy, supply, and access changes can move public obesity-drug "
            "and adjacent consumer-health exposure."
        ),
    },
    {
        "query_id": "crypto_market_structure_policy",
        "query": 'stablecoin crypto market structure bill SEC CFTC',
        "primary_entity": "crypto_market_structure_policy",
        "theme": "crypto_regulation",
        "relation_type": "regulatory_policy_to_public_crypto_exposure",
        "candidate_tickers": ["COIN", "MSTR", "HOOD", "IBIT", "MARA", "RIOT"],
        "rationale": (
            "Crypto policy headlines often start as sector/regulatory news, not "
            "ticker-specific items."
        ),
    },
]


def _date_tag(today: str | datetime | None) -> str:
    if today is None:
        return datetime.now().strftime("%Y%m%d")
    if isinstance(today, datetime):
        return today.strftime("%Y%m%d")
    text = str(today)
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    return text


def _google_news_url(query: str) -> str:
    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )


def get_entity_theme_observer_sources() -> list[dict]:
    sources = []
    for spec in ENTITY_THEME_SOURCE_SPECS:
        metadata = {
            "observer_only": True,
            "observer_name": OBSERVER_NAME,
            "schema_version": SCHEMA_VERSION,
            "query_id": spec["query_id"],
            "query": spec["query"],
            "primary_entity": spec["primary_entity"],
            "theme": spec["theme"],
            "relation_type": spec["relation_type"],
            "candidate_tickers": list(spec["candidate_tickers"]),
            "keywords": list(spec["candidate_tickers"]),
            "rationale": spec["rationale"],
        }
        sources.append(
            {
                "url": _google_news_url(spec["query"]),
                "source_type": "google_news_entity_theme",
                "metadata": metadata,
            }
        )
    return sources


def _artifact_paths(date_tag: str, data_dir: str | Path | None = None) -> dict[str, Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    base = root / ARTIFACT_ROOT
    return {
        "items": base / "daily" / f"{OBSERVER_NAME}_{date_tag}.json",
        "source_stats": base
        / "source_stats"
        / f"{OBSERVER_NAME}_source_stats_{date_tag}.json",
        "source_manifest": base / "source_manifest.json",
        "latest_summary": base / "latest_summary.json",
        "outcome_ledger": base
        / "outcome_ledgers"
        / f"{OBSERVER_NAME}_outcomes_{date_tag}.jsonl",
        "outcome_summary": base
        / "outcome_summaries"
        / f"{OBSERVER_NAME}_outcome_summary_{date_tag}.json",
        "latest_outcome_summary": base / "latest_outcome_summary.json",
    }


def _remove_write_temps(path: Path) -> None:
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def _write_json(payload: Any, path: Path) -> None:
    try:
        atomic_write_json(payload, path, default=str)
        _remove_write_temps(path)
        return
    except PermissionError:
        log.warning("Atomic write failed for %s; falling back to direct write", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    _remove_write_temps(path)


def _annotate_item(item: dict, metadata: dict) -> dict:
    annotated = dict(item)
    annotated.update(
        {
            "observer_only": True,
            "observer_name": OBSERVER_NAME,
            "observer_schema_version": SCHEMA_VERSION,
            "entity_theme_query_id": metadata.get("query_id"),
            "entity_theme_query": metadata.get("query"),
            "primary_entity": metadata.get("primary_entity"),
            "theme": metadata.get("theme"),
            "relation_type": metadata.get("relation_type"),
            "candidate_tickers": list(metadata.get("candidate_tickers") or []),
        }
    )
    return annotated


def persist_entity_theme_news_observer(
    today: str | datetime | None = None,
    *,
    data_dir: str | Path | None = None,
    parse_func=None,
) -> dict:
    """Fetch entity/theme feeds and persist observer-only daily artifacts."""
    if parse_func is None:
        from parser import parse_feed_with_diagnostics as parse_func
        from parser import deduplicate_items, sort_items_by_date
    else:
        from parser import deduplicate_items, sort_items_by_date

    date_tag = _date_tag(today)
    sources = get_entity_theme_observer_sources()
    raw_items: list[dict] = []
    source_stats: list[dict] = []

    for source in sources:
        metadata = dict(source.get("metadata") or {})
        try:
            items, diagnostics = parse_func(
                source["url"],
                source["source_type"],
                metadata,
            )
        except Exception as exc:
            log.warning("Entity/theme source failed: %s", exc)
            items = []
            diagnostics = {
                "url": source["url"],
                "source_type": source["source_type"],
                "metadata": metadata,
                "request_headers_used": {},
                "status": None,
                "bozo": False,
                "bozo_exception": None,
                "entry_count": 0,
                "parsed_item_count": 0,
                "error": str(exc),
            }
        source_stats.append(diagnostics)
        raw_items.extend(_annotate_item(item, metadata) for item in items)

    unique_items = sort_items_by_date(deduplicate_items(raw_items))
    source_manifest = {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "sources": sources,
    }
    paths = _artifact_paths(date_tag, data_dir)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "status": "ok",
        "date": date_tag,
        "source_count": len(sources),
        "source_error_count": sum(1 for stat in source_stats if stat.get("error")),
        "raw_item_count": len(raw_items),
        "unique_item_count": len(unique_items),
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "items_path": str(paths["items"]),
        "source_stats_path": str(paths["source_stats"]),
        "source_manifest_path": str(paths["source_manifest"]),
    }

    atomic_write_json(unique_items, paths["items"], default=str)
    atomic_write_json(source_stats, paths["source_stats"], default=str)
    atomic_write_json(source_manifest, paths["source_manifest"], default=str)
    atomic_write_json(summary, paths["latest_summary"], default=str)
    return summary


def _date10(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _bar_date(row: dict[str, Any]) -> str | None:
    for key in ("Date", "date", "timestamp"):
        parsed = _date10(row.get(key))
        if parsed:
            return parsed
    return None


def _bar_float(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _normalise_bars(
    ohlcv_by_ticker: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    cutoff = _date10(as_of_date)
    normalised: dict[str, list[dict[str, Any]]] = {}
    for ticker, payload in (ohlcv_by_ticker or {}).items():
        rows: list[Any]
        if isinstance(payload, dict):
            rows = list(payload.values())
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        clean_rows = []
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            day = _bar_date(raw)
            if not day or (cutoff and day > cutoff):
                continue
            clean_rows.append({**raw, "_date": day})
        clean_rows.sort(key=lambda row: row["_date"])
        normalised[str(ticker).upper()] = clean_rows
    return normalised


def _entry_index(rows: list[dict[str, Any]], observed_date: str) -> int | None:
    for index, row in enumerate(rows):
        if row["_date"] > observed_date:
            return index
    return None


def _bar_by_date(rows: list[dict[str, Any]], target_date: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("_date") == target_date:
            return row
    return None


def _next_market_date(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    observed_date: str,
) -> str | None:
    dates: list[str] = []
    benchmark_rows = [
        row
        for ticker in ("SPY", "QQQ")
        for row in bars_by_ticker.get(ticker, [])
    ]
    rows = benchmark_rows or [
        row for ticker_rows in bars_by_ticker.values() for row in ticker_rows
    ]
    for row in rows:
        day = row.get("_date")
        if isinstance(day, str) and day > observed_date:
            dates.append(day)
    return min(dates) if dates else None


def _missing_entry_status(
    ticker_bars: list[dict[str, Any]],
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    observed_date: str,
) -> tuple[str, str]:
    if not ticker_bars:
        return "unsettled_no_entry_bar", "ticker_has_no_price_rows"
    if _next_market_date(bars_by_ticker, observed_date) is None:
        return (
            "future_entry_session_not_reached",
            "market_calendar_has_no_session_after_observed_date",
        )
    return (
        "unsettled_no_entry_bar",
        "market_calendar_has_next_session_but_ticker_missing_bar",
    )


def _pnl_for_bars(
    entry_bar: dict[str, Any],
    exit_bar: dict[str, Any],
    notional: float,
) -> float | None:
    entry_open = _bar_float(entry_bar, "Open", "open")
    exit_close = _bar_float(exit_bar, "Close", "close")
    if not entry_open or not exit_close:
        return None
    return round(notional * (exit_close / entry_open - 1.0), 2)


def build_entity_theme_news_outcome_ledger(
    items: list[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    *,
    as_of_date: str | None = None,
    horizons: tuple[int, ...] = (10,),
    notional_usd: float = 4000.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build observer-only forward outcomes for entity/theme news rows."""
    bars = _normalise_bars(ohlcv_by_ticker, as_of_date=as_of_date)
    rows: list[dict[str, Any]] = []
    horizon_values = tuple(sorted({int(horizon) for horizon in horizons if int(horizon) > 0}))
    for item_index, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        observed_date = (
            _date10(item.get("published_at"))
            or _date10(item.get("observed_at"))
            or _date10(item.get("date"))
            or _date10(as_of_date)
        )
        if not observed_date:
            continue
        candidate_tickers = [
            str(ticker).upper()
            for ticker in (item.get("candidate_tickers") or [])
            if str(ticker).strip()
        ]
        for ticker in candidate_tickers:
            ticker_bars = bars.get(ticker, [])
            entry_idx = _entry_index(ticker_bars, observed_date)
            for horizon in horizon_values:
                base = {
                    "observer_only": True,
                    "observer_name": OBSERVER_NAME,
                    "outcome_rule_version": OUTCOME_RULE_VERSION,
                    "entity_theme_query_id": item.get("entity_theme_query_id"),
                    "primary_entity": item.get("primary_entity"),
                    "theme": item.get("theme"),
                    "relation_type": item.get("relation_type"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "published_at": item.get("published_at"),
                    "observed_date": observed_date,
                    "candidate_ticker": ticker,
                    "candidate_item_index": item_index,
                    "horizon_trading_days": horizon,
                    "notional_usd": notional_usd,
                    "trade_enabled": False,
                }
                if entry_idx is None:
                    status, detail = _missing_entry_status(
                        ticker_bars,
                        bars,
                        observed_date,
                    )
                    rows.append(
                        {
                            **base,
                            "outcome_status": status,
                            "outcome_status_detail": detail,
                        }
                    )
                    continue
                exit_idx = entry_idx + horizon - 1
                entry_bar = ticker_bars[entry_idx]
                base["entry_date"] = entry_bar["_date"]
                base["entry_open"] = _bar_float(entry_bar, "Open", "open")
                if exit_idx >= len(ticker_bars):
                    rows.append({**base, "outcome_status": "unsettled_horizon"})
                    continue
                exit_bar = ticker_bars[exit_idx]
                pnl = _pnl_for_bars(entry_bar, exit_bar, notional_usd)
                base.update(
                    {
                        "exit_date": exit_bar["_date"],
                        "exit_close": _bar_float(exit_bar, "Close", "close"),
                        "pnl_usd": pnl,
                        "replacement_value_vs_cash_usd": pnl,
                    }
                )
                comparator_detail: dict[str, Any] = {}
                missing_comparator = False
                for comparator in ("SPY", "QQQ"):
                    comp_rows = bars.get(comparator, [])
                    comp_entry = _bar_by_date(comp_rows, entry_bar["_date"])
                    comp_exit = _bar_by_date(comp_rows, exit_bar["_date"])
                    comp_pnl = (
                        _pnl_for_bars(comp_entry, comp_exit, notional_usd)
                        if comp_entry and comp_exit
                        else None
                    )
                    if comp_pnl is None or pnl is None:
                        missing_comparator = True
                    field = f"replacement_value_vs_{comparator.lower()}_usd"
                    base[field] = (
                        round(pnl - comp_pnl, 2)
                        if pnl is not None and comp_pnl is not None
                        else None
                    )
                    comparator_detail[comparator] = {
                        "entry_date": entry_bar["_date"] if comp_entry else None,
                        "exit_date": exit_bar["_date"] if comp_exit else None,
                        "pnl_usd": comp_pnl,
                    }
                base["comparator_detail"] = comparator_detail
                base["outcome_status"] = (
                    "missing_comparator_bars" if missing_comparator else "settled"
                )
                rows.append(base)

    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("outcome_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "observer_only": True,
        "observer_name": OBSERVER_NAME,
        "outcome_rule_version": OUTCOME_RULE_VERSION,
        "source_item_count": len(items or []),
        "candidate_outcome_row_count": len(rows),
        "settled_count": status_counts.get("settled", 0),
        "unsettled_count": sum(
            count for status, count in status_counts.items() if status != "settled"
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "horizons": list(horizon_values),
        "notional_usd": notional_usd,
        "as_of_date": _date10(as_of_date),
        "strategy_behavior_changed": False,
        "trade_enabled": False,
    }
    return rows, summary


def _daily_item_file_date(path: Path) -> str | None:
    stem = path.stem
    prefix = f"{OBSERVER_NAME}_"
    if not stem.startswith(prefix):
        return None
    return _date10(stem[len(prefix) :])


def _daily_item_paths_through(
    date_tag: str,
    *,
    data_dir: str | Path | None = None,
) -> list[Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    daily_dir = root / ARTIFACT_ROOT / "daily"
    cutoff = _date10(date_tag)
    if not daily_dir.exists():
        return []
    paths = []
    for path in daily_dir.glob(f"{OBSERVER_NAME}_*.json"):
        file_date = _daily_item_file_date(path)
        if not file_date:
            continue
        if cutoff and file_date > cutoff:
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: (_daily_item_file_date(path) or "", path.name))


def _load_daily_items_through(
    date_tag: str,
    *,
    data_dir: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for path in _daily_item_paths_through(date_tag, data_dir=data_dir):
        file_date = _daily_item_file_date(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            files.append(
                {
                    "path": str(path),
                    "date": file_date,
                    "status": "error",
                    "item_count": 0,
                    "error": str(exc),
                }
            )
            continue
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            raw_rows = payload.get("items") or payload.get("rows") or []
            rows = [row for row in raw_rows if isinstance(row, dict)]
        else:
            rows = []
        for row in rows:
            item = dict(row)
            item.setdefault("observer_item_file_date", file_date)
            item.setdefault("date", file_date)
            items.append(item)
        files.append(
            {
                "path": str(path),
                "date": file_date,
                "status": "ok",
                "item_count": len(rows),
                "error": None,
            }
        )
    return items, files


def _candidate_tickers_for_outcomes(items: list[dict[str, Any]]) -> list[str]:
    tickers = {
        str(ticker).upper()
        for item in items
        for ticker in (item.get("candidate_tickers") or [])
        if str(ticker).strip()
    }
    tickers.update({"SPY", "QQQ"})
    return sorted(tickers)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _table_columns(con: sqlite3.Connection, table: str) -> dict[str, str]:
    return {
        str(row[1]).lower(): str(row[1])
        for row in con.execute(f"pragma table_info({_quote_identifier(table)})")
    }


def _load_warehouse_bars_from_table(
    con: sqlite3.Connection,
    *,
    table: str,
    tickers: list[str],
) -> list[dict[str, Any]]:
    columns = _table_columns(con, table)

    def column(*names: str) -> str | None:
        for name in names:
            if name.lower() in columns:
                return columns[name.lower()]
        return None

    ticker_col = column("ticker", "symbol")
    date_col = column("date", "Date", "timestamp")
    open_col = column("open", "Open")
    high_col = column("high", "High")
    low_col = column("low", "Low")
    close_col = column("close", "Close")
    volume_col = column("volume", "Volume")
    required = [ticker_col, date_col, open_col, high_col, low_col, close_col]
    if any(value is None for value in required):
        return []
    placeholders = ",".join("?" for _ in tickers)
    select_volume = _quote_identifier(volume_col) if volume_col else "null"
    query = f"""
        select
            {_quote_identifier(ticker_col)} as ticker,
            {_quote_identifier(date_col)} as date,
            {_quote_identifier(open_col)} as open,
            {_quote_identifier(high_col)} as high,
            {_quote_identifier(low_col)} as low,
            {_quote_identifier(close_col)} as close,
            {select_volume} as volume
        from {_quote_identifier(table)}
        where upper({_quote_identifier(ticker_col)}) in ({placeholders})
        order by {_quote_identifier(ticker_col)}, {_quote_identifier(date_col)}
    """
    params = [ticker.upper() for ticker in tickers]
    return [
        {
            "ticker": str(ticker).upper(),
            "date": date,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
        for ticker, date, open_, high, low, close, volume in con.execute(query, params)
    ]


def _default_warehouse_paths(data_dir: str | Path | None = None) -> list[Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    return [
        root / "warehouse" / "warehouse_main_hot.sqlite",
        root / "warehouse" / "warehouse_main.sqlite",
        root / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite",
    ]


def _load_warehouse_bars_for_tickers(
    tickers: list[str],
    *,
    data_dir: str | Path | None = None,
    warehouse_paths: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not tickers:
        return {}, {"status": "no_tickers", "sources": []}
    paths = [Path(path) for path in (warehouse_paths or _default_warehouse_paths(data_dir))]
    requested = sorted({str(ticker).upper() for ticker in tickers if str(ticker).strip()})
    bars: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in requested}
    seen: set[tuple[str, str]] = set()
    sources: list[dict[str, Any]] = []
    for path in paths:
        source = {
            "path": str(path),
            "exists": path.exists(),
            "tables": [],
            "returned_rows": 0,
        }
        if not path.exists():
            sources.append(source)
            continue
        try:
            with sqlite3.connect(path) as con:
                tables = {
                    str(row[0])
                    for row in con.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
                for table in ("ohlcv", "ohlcv_snapshot_versions"):
                    if table not in tables:
                        continue
                    row_count = int(
                        con.execute(
                            f"select count(*) from {_quote_identifier(table)}"
                        ).fetchone()[0]
                    )
                    table_info = {
                        "table": table,
                        "row_count": row_count,
                        "returned_rows": 0,
                    }
                    if row_count > 0:
                        rows = _load_warehouse_bars_from_table(
                            con,
                            table=table,
                            tickers=requested,
                        )
                        for row in rows:
                            day = _date10(row.get("date"))
                            ticker = str(row.get("ticker") or "").upper()
                            if not day or ticker not in bars:
                                continue
                            key = (ticker, day)
                            if key in seen:
                                continue
                            seen.add(key)
                            bars[ticker].append(row)
                        table_info["returned_rows"] = len(rows)
                        source["returned_rows"] += len(rows)
                    source["tables"].append(table_info)
        except Exception as exc:
            source["error"] = str(exc)
        sources.append(source)
    for rows in bars.values():
        rows.sort(key=lambda row: _date10(row.get("date")) or "")
    all_dates = [
        _date10(row.get("date"))
        for ticker_rows in bars.values()
        for row in ticker_rows
        if _date10(row.get("date"))
    ]
    returned_tickers = sorted(ticker for ticker, rows in bars.items() if rows)
    return bars, {
        "status": "ok" if all_dates else "no_bars",
        "requested_tickers": len(requested),
        "returned_tickers": len(returned_tickers),
        "returned_rows": sum(len(rows) for rows in bars.values()),
        "date_min": min(all_dates) if all_dates else None,
        "date_max": max(all_dates) if all_dates else None,
        "sources": sources,
    }


def persist_entity_theme_news_outcome_ledger(
    today: str | datetime | None = None,
    *,
    data_dir: str | Path | None = None,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    warehouse_paths: list[str | Path] | tuple[str | Path, ...] | None = None,
    horizons: tuple[int, ...] = (10,),
    notional_usd: float = 4000.0,
) -> dict[str, Any]:
    """Refresh the observer-only forward outcome ledger through ``today``."""
    date_tag = _date_tag(today)
    items, item_files = _load_daily_items_through(date_tag, data_dir=data_dir)
    tickers = _candidate_tickers_for_outcomes(items)
    if ohlcv_by_ticker is None:
        bars, warehouse_summary = _load_warehouse_bars_for_tickers(
            tickers,
            data_dir=data_dir,
            warehouse_paths=warehouse_paths,
        )
    else:
        bars = ohlcv_by_ticker
        warehouse_summary = {
            "status": "provided",
            "requested_tickers": len(tickers),
            "returned_tickers": len(
                [ticker for ticker, rows in bars.items() if rows]
            ),
            "returned_rows": sum(
                len(rows) for rows in bars.values() if isinstance(rows, list)
            ),
            "sources": [],
        }
    rows, summary = build_entity_theme_news_outcome_ledger(
        items,
        bars,
        as_of_date=date_tag,
        horizons=horizons,
        notional_usd=notional_usd,
    )
    paths = _artifact_paths(date_tag, data_dir)
    summary.update(
        {
            "status": "ok" if item_files else "missing_items",
            "date": date_tag,
            "daily_item_file_count": len(item_files),
            "daily_item_files": item_files,
            "candidate_ticker_count": len(tickers),
            "warehouse": warehouse_summary,
            "ledger_path": str(paths["outcome_ledger"]),
            "summary_path": str(paths["outcome_summary"]),
            "latest_summary_path": str(paths["latest_outcome_summary"]),
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        }
    )
    write_entity_theme_news_outcome_ledger(
        rows,
        summary,
        ledger_path=paths["outcome_ledger"],
        summary_path=paths["outcome_summary"],
    )
    _write_json(summary, paths["latest_outcome_summary"])
    return summary


def write_entity_theme_news_outcome_ledger(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    ledger_path: str | Path,
    summary_path: str | Path,
) -> None:
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    _remove_write_temps(ledger)
    _write_json(summary, Path(summary_path))


__all__ = [
    "ENTITY_THEME_SOURCE_SPECS",
    "OBSERVER_NAME",
    "OUTCOME_RULE_VERSION",
    "build_entity_theme_news_outcome_ledger",
    "get_entity_theme_observer_sources",
    "persist_entity_theme_news_observer",
    "persist_entity_theme_news_outcome_ledger",
    "write_entity_theme_news_outcome_ledger",
]
