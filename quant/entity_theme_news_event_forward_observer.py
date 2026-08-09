"""Prospective, default-off entity/theme news event forward observer.

One exact URL is one paper decision.  Availability is established only by the
policy clock (``first_seen_at``); publisher timestamps are retained solely as
freshness metadata and never choose an entry session.  Each event receives one
fixed paper notional split equally, to the cent, across its unique mapped
tickers.  Decision rows are immutable and outcome rows are appended only once
all ten trading sessions and both benchmark comparators are available.

This is an alpha-enabling measurement surface, not an executable strategy.
Every persisted row is ``trade_enabled=False`` and no order/ranking/sizing
surface is imported or modified here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text
from entity_theme_news_observer import (
    OBSERVER_NAME as SOURCE_OBSERVER_NAME,
    _load_warehouse_bars_for_tickers,
    _normalise_bars,
)


SCHEMA_VERSION = 1
OBSERVER_NAME = "entity_theme_news_event_forward_observer"
RULE_VERSION = "entity_theme_news_first_seen_exact_url_event_v1"
SOURCE_DAILY_RELATIVE = Path("non_ohlcv") / SOURCE_OBSERVER_NAME / "daily"
OUTPUT_RELATIVE = Path("non_ohlcv") / OBSERVER_NAME
DEFAULT_EVENT_NOTIONAL_USD = 4000.0
DEFAULT_FRESHNESS_HOURS = 36.0
DEFAULT_HOLD_SESSIONS = 10
TARGET_PRICE_STATUS = "fixed_10_session_time_exit_not_target_driven"
MARKET_TZ = ZoneInfo("America/New_York")


def exact_url_decision_id(url: str) -> str:
    """Return the stable SHA-256 decision id for an exact URL string."""
    return hashlib.sha256(str(url).strip().encode("utf-8")).hexdigest()


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y%m%d", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _cutoff_date(today: str | datetime | date | None, observed: datetime) -> str:
    if today is None:
        return observed.date().isoformat()
    if isinstance(today, datetime):
        return today.date().isoformat()
    if isinstance(today, date):
        return today.isoformat()
    text = str(today).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"invalid today value: {today!r}")


def _daily_file_date(path: Path) -> str | None:
    prefix = f"{SOURCE_OBSERVER_NAME}_"
    stem = path.stem
    if not stem.startswith(prefix):
        return None
    suffix = stem[len(prefix) :]
    try:
        return datetime.strptime(suffix, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _daily_paths(data_root: Path, cutoff: str) -> list[Path]:
    directory = data_root / SOURCE_DAILY_RELATIVE
    if not directory.exists():
        return []
    paths = []
    for path in directory.glob(f"{SOURCE_OBSERVER_NAME}_*.json"):
        file_date = _daily_file_date(path)
        if file_date and file_date <= cutoff:
            paths.append(path)
    return sorted(paths, key=lambda path: (_daily_file_date(path) or "", path.name))


def _load_items(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("items") or payload.get("rows") or []
    else:
        rows = []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "seen_urls": {}}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"observer state must be a JSON object: {path}")
    seen = payload.get("seen_urls")
    if not isinstance(seen, dict):
        seen = {}
    return {**payload, "schema_version": SCHEMA_VERSION, "seen_urls": seen}


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"malformed append-only ledger row {path}:{line_number}"
                ) from exc
            if not isinstance(row, dict) or not row.get("record_id"):
                raise ValueError(
                    f"invalid append-only ledger row {path}:{line_number}"
                )
            rows.append(row)
    return rows


def _prior_seen_urls(paths: list[Path]) -> dict[str, dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for path in paths:
        for item in _load_items(path):
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            decision_id = exact_url_decision_id(url)
            seen.setdefault(
                decision_id,
                {
                    "decision_id": decision_id,
                    "first_seen_at": None,
                    "first_seen_source": "historical_daily_file_presence",
                    "source_daily_file": str(path),
                    "decision_created": False,
                },
            )
    return seen


def _allocate_event_notional(
    tickers: list[str], event_notional_usd: float
) -> list[dict[str, Any]]:
    unique = sorted({str(ticker).upper().strip() for ticker in tickers if str(ticker).strip()})
    if not unique:
        return []
    total_cents = int(round(float(event_notional_usd) * 100.0))
    base, remainder = divmod(total_cents, len(unique))
    return [
        {
            "ticker": ticker,
            "paper_notional_usd": (base + (1 if index < remainder else 0)) / 100.0,
        }
        for index, ticker in enumerate(unique)
    ]


def _decision_contract(
    item: dict[str, Any],
    *,
    observed: datetime,
    source_path: Path,
    freshness_hours: float,
    event_notional_usd: float,
    hold_sessions: int,
) -> tuple[dict[str, Any] | None, str | None]:
    url = str(item.get("url") or "").strip()
    if not url:
        return None, "missing_url"
    published = _parse_timestamp(item.get("published_at"))
    if published is None:
        return None, "missing_or_invalid_published_at_freshness_metadata"
    age_hours = (observed - published).total_seconds() / 3600.0
    if age_hours < 0.0:
        return None, "published_after_policy_observation"
    if age_hours > freshness_hours:
        return None, "outside_freshness_window"
    legs = _allocate_event_notional(
        list(item.get("candidate_tickers") or []), event_notional_usd
    )
    if not legs:
        return None, "missing_candidate_tickers"
    decision_id = exact_url_decision_id(url)
    first_seen_at = _iso_utc(observed)
    contract = {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "rule_version": RULE_VERSION,
        "decision_id": decision_id,
        "event_id": decision_id,
        "url_sha256": decision_id,
        "url": url,
        "title": item.get("title"),
        "entity_theme_query_id": item.get("entity_theme_query_id"),
        "primary_entity": item.get("primary_entity"),
        "theme": item.get("theme"),
        "relation_type": item.get("relation_type"),
        "first_seen_at": first_seen_at,
        "observed_at": first_seen_at,
        "availability_timestamp_field": "first_seen_at",
        "availability_timestamp_source": "first_seen_at",
        "published_at": _iso_utc(published),
        "published_at_role": "freshness_metadata_only_not_availability",
        "freshness_age_hours": round(age_hours, 6),
        "freshness_limit_hours": float(freshness_hours),
        "source_daily_file": str(source_path),
        "entry_rule": "next_trading_session_open_after_first_seen_at",
        "exit_rule": f"close_after_{int(hold_sessions)}_trading_sessions",
        "hold_sessions": int(hold_sessions),
        "target_price": None,
        "target_price_status": TARGET_PRICE_STATUS,
        "event_paper_notional_usd": round(float(event_notional_usd), 2),
        "paper_event_notional_usd": round(float(event_notional_usd), 2),
        "event_notional_usd": round(float(event_notional_usd), 2),
        "candidate_tickers": [leg["ticker"] for leg in legs],
        "leg_count": len(legs),
        "legs": legs,
        "outcome_status": "pending_10_trading_sessions",
        "entry_date": None,
        "entry_date_status": "pending_next_session_open_after_first_seen_at",
        "observer_only": True,
        "trade_enabled": False,
    }
    return contract, None


def _decision_rows(decision: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for leg in decision["legs"]:
        ticker = leg["ticker"]
        rows.append(
            {
                **{key: value for key, value in decision.items() if key != "legs"},
                "row_type": "decision",
                "record_id": f"decision:{decision['decision_id']}:{ticker}",
                "ticker": ticker,
                "candidate_ticker": ticker,
                "paper_notional_usd": leg["paper_notional_usd"],
                "notional_usd": leg["paper_notional_usd"],
            }
        )
    return rows


def _bar_by_date(rows: list[dict[str, Any]], target: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("_date") == target), None)


def _number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _entry_and_exit_dates(
    first_seen_at: str,
    bars: dict[str, list[dict[str, Any]]],
    hold_sessions: int,
) -> tuple[str | None, str | None, str]:
    observed = _parse_timestamp(first_seen_at)
    if observed is None:
        return None, None, "invalid_first_seen_at"
    benchmark = bars.get("SPY") or bars.get("QQQ") or []
    sessions = sorted({str(row.get("_date")) for row in benchmark if row.get("_date")})
    local = observed.astimezone(MARKET_TZ)
    local_date = local.date().isoformat()
    before_open = local.timetz().replace(tzinfo=None) < time(9, 30)
    if before_open:
        eligible = [session for session in sessions if session >= local_date]
    else:
        eligible = [session for session in sessions if session > local_date]
    if not eligible:
        return None, None, "next_session_not_available"
    entry_date = eligible[0]
    entry_index = sessions.index(entry_date)
    exit_index = entry_index + int(hold_sessions) - 1
    if exit_index >= len(sessions):
        return entry_date, None, "holding_window_not_complete"
    return entry_date, sessions[exit_index], "ready"


def _settle_decision_row(
    row: dict[str, Any], bars: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, Any] | None, str]:
    hold_sessions = int(row.get("hold_sessions") or DEFAULT_HOLD_SESSIONS)
    entry_date, exit_date, status = _entry_and_exit_dates(
        str(row.get("first_seen_at") or ""), bars, hold_sessions
    )
    if status != "ready" or not entry_date or not exit_date:
        return None, status
    ticker = str(row.get("ticker") or "").upper()
    ticker_entry = _bar_by_date(bars.get(ticker, []), entry_date)
    ticker_exit = _bar_by_date(bars.get(ticker, []), exit_date)
    spy_entry = _bar_by_date(bars.get("SPY", []), entry_date)
    spy_exit = _bar_by_date(bars.get("SPY", []), exit_date)
    qqq_entry = _bar_by_date(bars.get("QQQ", []), entry_date)
    qqq_exit = _bar_by_date(bars.get("QQQ", []), exit_date)
    required = (ticker_entry, ticker_exit, spy_entry, spy_exit, qqq_entry, qqq_exit)
    if any(bar is None for bar in required):
        return None, "missing_aligned_ticker_or_comparator_bar"
    entry_open = _number(ticker_entry or {}, "Open", "open")
    exit_close = _number(ticker_exit or {}, "Close", "close")
    spy_open = _number(spy_entry or {}, "Open", "open")
    spy_close = _number(spy_exit or {}, "Close", "close")
    qqq_open = _number(qqq_entry or {}, "Open", "open")
    qqq_close = _number(qqq_exit or {}, "Close", "close")
    if not all(value and value > 0 for value in (entry_open, exit_close, spy_open, spy_close, qqq_open, qqq_close)):
        return None, "missing_or_nonpositive_price"
    notional = float(row.get("paper_notional_usd") or 0.0)
    pnl = notional * (float(exit_close) / float(entry_open) - 1.0)
    spy_pnl = notional * (float(spy_close) / float(spy_open) - 1.0)
    qqq_pnl = notional * (float(qqq_close) / float(qqq_open) - 1.0)
    decision_id = str(row["decision_id"])
    outcome = {
        **{key: value for key, value in row.items() if key != "record_id"},
        "row_type": "outcome",
        "record_id": f"outcome:{decision_id}:{ticker}:{hold_sessions}",
        "entry_date": entry_date,
        "entry_open": round(float(entry_open), 8),
        "exit_date": exit_date,
        "exit_close": round(float(exit_close), 8),
        "pnl_usd": round(pnl, 2),
        "replacement_value_vs_cash_usd": round(pnl, 2),
        "replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2),
        "replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2),
        "comparator_detail": {
            "SPY": {
                "entry_open": round(float(spy_open), 8),
                "exit_close": round(float(spy_close), 8),
                "pnl_usd": round(spy_pnl, 2),
            },
            "QQQ": {
                "entry_open": round(float(qqq_open), 8),
                "exit_close": round(float(qqq_close), 8),
                "pnl_usd": round(qqq_pnl, 2),
            },
        },
        "outcome_status": "settled",
        "trade_enabled": False,
    }
    return outcome, "settled"


def persist_entity_theme_news_event_forward_observer(
    today: str | datetime | date | None = None,
    *,
    observed_at: str | datetime | None = None,
    data_dir: str | Path | None = None,
    state_path: str | Path | None = None,
    ledger_path: str | Path | None = None,
    summary_path: str | Path | None = None,
    source_daily_path: str | Path | None = None,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    warehouse_paths: list[str | Path] | tuple[str | Path, ...] | None = None,
    freshness_hours: float = DEFAULT_FRESHNESS_HOURS,
    event_notional_usd: float = DEFAULT_EVENT_NOTIONAL_USD,
    hold_sessions: int = DEFAULT_HOLD_SESSIONS,
) -> dict[str, Any]:
    """Append unseen URL decisions and any newly mature ten-session outcomes."""
    observed = _parse_timestamp(observed_at) if observed_at is not None else None
    if observed is None:
        observed = datetime.now(timezone.utc)
    if freshness_hours <= 0 or event_notional_usd <= 0 or hold_sessions <= 0:
        raise ValueError("freshness, event notional, and hold sessions must be positive")
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    output = root / OUTPUT_RELATIVE
    state_file = Path(state_path) if state_path is not None else output / "state.json"
    ledger_file = Path(ledger_path) if ledger_path is not None else output / "ledger.jsonl"
    summary_file = Path(summary_path) if summary_path is not None else output / "latest_summary.json"
    cutoff = _cutoff_date(today, observed)

    if source_daily_path is not None:
        source_path = Path(source_daily_path)
        available_paths = _daily_paths(root, cutoff)
        prior_paths = [path for path in available_paths if path.resolve() != source_path.resolve() and (_daily_file_date(path) or "") < (_daily_file_date(source_path) or cutoff)]
    else:
        available_paths = _daily_paths(root, cutoff)
        source_path = available_paths[-1] if available_paths else None
        prior_paths = available_paths[:-1]

    state = _load_state(state_file)
    ledger_rows = _load_ledger(ledger_file)
    existing_record_ids = {str(row["record_id"]) for row in ledger_rows}
    existing_decision_ids = {
        str(row.get("decision_id"))
        for row in ledger_rows
        if row.get("row_type") == "decision" and row.get("decision_id")
    }
    seen_urls: dict[str, Any] = dict(state.get("seen_urls") or {})
    for decision_id, metadata in _prior_seen_urls(prior_paths).items():
        seen_urls.setdefault(decision_id, metadata)

    new_decisions: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    source_items: list[dict[str, Any]] = []
    if source_path is not None and source_path.exists():
        source_items = _load_items(source_path)
        current_unique: dict[str, dict[str, Any]] = {}
        for item in source_items:
            url = str(item.get("url") or "").strip()
            if not url:
                skipped["missing_url"] = skipped.get("missing_url", 0) + 1
                continue
            current_unique.setdefault(exact_url_decision_id(url), item)
        for decision_id, item in current_unique.items():
            if decision_id in seen_urls or decision_id in existing_decision_ids:
                skipped["already_seen"] = skipped.get("already_seen", 0) + 1
                continue
            decision, reason = _decision_contract(
                item,
                observed=observed,
                source_path=source_path,
                freshness_hours=float(freshness_hours),
                event_notional_usd=float(event_notional_usd),
                hold_sessions=int(hold_sessions),
            )
            seen_urls[decision_id] = {
                "decision_id": decision_id,
                "first_seen_at": _iso_utc(observed),
                "first_seen_source": "policy_observation_clock",
                "source_daily_file": str(source_path),
                "decision_created": decision is not None,
                "skip_reason": reason,
            }
            if decision is None:
                skipped[str(reason or "invalid")] = skipped.get(str(reason or "invalid"), 0) + 1
                continue
            new_decisions.append(decision)
            for row in _decision_rows(decision):
                if row["record_id"] not in existing_record_ids:
                    decision_rows.append(row)
                    existing_record_ids.add(row["record_id"])

    all_decision_rows = [
        row for row in ledger_rows + decision_rows if row.get("row_type") == "decision"
    ]
    requested_tickers = sorted(
        {
            str(row.get("ticker") or "").upper()
            for row in all_decision_rows
            if row.get("ticker")
        }
        | {"SPY", "QQQ"}
    )
    if ohlcv_by_ticker is None:
        raw_bars, warehouse_summary = _load_warehouse_bars_for_tickers(
            requested_tickers,
            data_dir=root,
            warehouse_paths=warehouse_paths,
        )
    else:
        raw_bars = ohlcv_by_ticker
        warehouse_summary = {
            "status": "provided",
            "requested_tickers": len(requested_tickers),
            "returned_tickers": sum(1 for rows in raw_bars.values() if rows is not None),
        }
    bars = _normalise_bars(raw_bars, as_of_date=cutoff)
    outcome_rows: list[dict[str, Any]] = []
    pending_status_counts: dict[str, int] = {}
    for row in all_decision_rows:
        record_id = f"outcome:{row['decision_id']}:{row['ticker']}:{int(row.get('hold_sessions') or hold_sessions)}"
        if record_id in existing_record_ids:
            continue
        outcome, outcome_status = _settle_decision_row(row, bars)
        if outcome is None:
            pending_status_counts[outcome_status] = pending_status_counts.get(outcome_status, 0) + 1
            continue
        outcome_rows.append(outcome)
        existing_record_ids.add(record_id)

    appended_rows = decision_rows + outcome_rows
    if appended_rows:
        existing_text = ledger_file.read_text(encoding="utf-8") if ledger_file.exists() else ""
        if existing_text and not existing_text.endswith("\n"):
            existing_text += "\n"
        atomic_write_text(
            existing_text
            + "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
                for row in appended_rows
            ),
            ledger_file,
        )

    all_rows = ledger_rows + appended_rows
    all_outcomes = [row for row in all_rows if row.get("row_type") == "outcome"]
    outcome_keys = {
        (str(row.get("decision_id")), str(row.get("ticker"))) for row in all_outcomes
    }
    pending_count = sum(
        1
        for row in all_decision_rows
        if (str(row.get("decision_id")), str(row.get("ticker"))) not in outcome_keys
    )
    decision_ids = {str(row.get("decision_id")) for row in all_decision_rows}
    settled_event_count = sum(
        1
        for decision_id in decision_ids
        if all(
            (decision_id, str(row.get("ticker"))) in outcome_keys
            for row in all_decision_rows
            if str(row.get("decision_id")) == decision_id
        )
    )
    state.update(
        {
            "schema_version": SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "updated_at": _iso_utc(observed),
            "seen_urls": seen_urls,
            "trade_enabled": False,
        }
    )
    atomic_write_json(state, state_file, default=str)
    summary = {
        "status": "ok" if source_path is not None else "missing_daily_input",
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": cutoff,
        "observed_at": _iso_utc(observed),
        "availability_timestamp_field": "first_seen_at",
        "availability_timestamp_source": "first_seen_at",
        "published_at_role": "freshness_metadata_only_not_availability",
        "source_daily_path": str(source_path) if source_path is not None else None,
        "source_item_count": len(source_items),
        "prior_daily_file_count": len(prior_paths),
        "decision_count": len(new_decisions),
        "event_count": len(new_decisions),
        "new_event_count": len(new_decisions),
        "leg_count": len(decision_rows),
        "ticker_leg_count": len(decision_rows),
        "decision_rows_appended": len(decision_rows),
        "outcome_rows_appended": len(outcome_rows),
        "rows_appended": len(appended_rows),
        "decision_count_total": len(decision_ids),
        "decision_leg_count_total": len(all_decision_rows),
        "settled_count": len(all_outcomes),
        "settled_event_count": settled_event_count,
        "pending_count": pending_count,
        "pending_status_counts": dict(sorted(pending_status_counts.items())),
        "skipped_counts": dict(sorted(skipped.items())),
        "event_notional_usd": round(float(event_notional_usd), 2),
        "freshness_hours": float(freshness_hours),
        "hold_sessions": int(hold_sessions),
        "decisions": new_decisions,
        "warehouse": warehouse_summary,
        "state_path": str(state_file),
        "ledger_path": str(ledger_file),
        "summary_path": str(summary_file),
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }
    atomic_write_json(summary, summary_file, default=str)
    return summary


__all__ = [
    "DEFAULT_EVENT_NOTIONAL_USD",
    "DEFAULT_FRESHNESS_HOURS",
    "DEFAULT_HOLD_SESSIONS",
    "OBSERVER_NAME",
    "RULE_VERSION",
    "TARGET_PRICE_STATUS",
    "exact_url_decision_id",
    "persist_entity_theme_news_event_forward_observer",
]
