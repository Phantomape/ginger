"""Experiment-local SEC periodic-report absorption leadership paper sleeve.

This helper owns the shared semantics for exp-20260611-012. It admits one
liquid stock after a PIT-safe 10-Q or 10-K filing only when the usable filing
date also shows price/volume absorption and SPY/QQQ relative leadership.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import macro_relief_leadership_paper_sleeve as leader
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from sec_event_queue import load_sec_filing_event_rows
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import macro_relief_leadership_paper_sleeve as leader
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from quant.sec_event_queue import load_sec_filing_event_rows


SLEEVE_NAME = "SEC_PERIODIC_REPORT_ABSORPTION_LEADERSHIP_PAPER"
RULE_VERSION = "sec_periodic_report_absorption_leadership_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "sec_periodic_report_absorption_leadership_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "sec_periodic_report_absorption_leadership" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "sec_periodic_report_absorption_leadership"
    / "snapshots.jsonl"
)

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "daily_entry_slots": 1,
    "max_active_positions": 8,
    "hold_days": 10,
    "same_ticker_cooldown_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "accepted_form_types": ("10-Q", "10-K"),
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "min_signal_return": 0.004,
    "min_relative_vs_spy": 0.006,
    "min_relative_vs_qqq": 0.002,
    "min_close_location": 0.66,
    "min_volume_ratio_20d": 0.90,
    "max_volume_ratio_20d": 4.50,
    "min_ret5": -0.035,
    "max_ret5": 0.130,
    "max_ret20": 0.350,
    "min_ret20_excess_spy": 0.020,
    "min_ret60_excess_spy": -0.020,
    "max_realized_vol_20d": 0.090,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_sec_periodic_report_absorption_leadership_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_sec_periodic_report_absorption_leadership_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": leader._date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "raw_candidate_count": 0,
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "sec_periodic_report_absorption_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_sec_periodic_report_absorption_leadership_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_sec_periodic_report_absorption_leadership_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_sec_periodic_report_absorption_leadership_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_sec_periodic_report_absorption_leadership_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(leader._safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_sec_periodic_report_absorption_leadership_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(leader._safe(snapshot), sort_keys=True) + "\n")


def build_sec_periodic_report_absorption_leadership_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    sec_filing_events: list[dict[str, Any]] | str | Path | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    core_entries: list[dict[str, Any]] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = leader._date10(as_of)
    working_state = deepcopy(
        state
        if state is not None
        else load_sec_periodic_report_absorption_leadership_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_sec_periodic_report_absorption_leadership_snapshot(
            as_of_date,
            "missing_ohlcv",
        )
    if "SPY" not in rows_by_ticker or "QQQ" not in rows_by_ticker:
        return empty_sec_periodic_report_absorption_leadership_snapshot(
            as_of_date,
            "missing_spy_or_qqq_ohlcv",
        )
    if sec_filing_events is None:
        return empty_sec_periodic_report_absorption_leadership_snapshot(
            as_of_date,
            "missing_sec_filing_events",
        )
    event_rows = _normalise_event_source(sec_filing_events)
    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    if not sector_map:
        return empty_sec_periodic_report_absorption_leadership_snapshot(
            as_of_date,
            "missing_sector_entries",
        )

    filled_today = leader._fill_pending_entries(working_state, rows_by_ticker, as_of_date, cfg)
    closed_today = leader._advance_open_positions(working_state, rows_by_ticker, as_of_date, cfg)
    candidates, contexts, scan = build_sec_periodic_report_absorption_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        sec_filing_events=event_rows,
        dates=[as_of_date],
        sector_entries=sector_map,
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
    )
    selected_rows, rejected = select_sec_periodic_report_absorption_signal_rows(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        existing_state=working_state,
        config=cfg,
    )
    if len(working_state.get("pending_entries") or []) + len(
        working_state.get("open_positions") or []
    ) >= int(cfg["max_active_positions"]):
        rejected.extend({**row, "filter_reason": "max_active_positions"} for row in selected_rows)
        selected_rows = []

    new_pending_entries: list[dict[str, Any]] = []
    if cfg.get("paper_enabled", True):
        for row in selected_rows:
            pending = _pending_entry_from_candidate(row, cfg)
            if not leader._has_pending_open_or_closed_decision(
                working_state,
                pending["decision_id"],
            ):
                working_state["pending_entries"].append(pending)
                new_pending_entries.append(pending)

    if not selected_rows and not contexts:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_periodic_report_context"))
    elif not selected_rows and contexts and not candidates:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_periodic_report_absorption_candidate"))

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        candidates=candidates,
        selected_rows=selected_rows,
        rejected=rejected,
        contexts=contexts,
        scan=scan,
        new_pending_entries=new_pending_entries,
        filled_today=filled_today,
        closed_today=closed_today,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
        config=cfg,
    )
    if persist:
        save_sec_periodic_report_absorption_leadership_state(working_state, state_path)
        append_sec_periodic_report_absorption_leadership_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_sec_periodic_report_absorption_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    sec_filing_events: list[dict[str, Any]] | str | Path,
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    event_rows = _normalise_event_source(sec_filing_events)
    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    all_trades: list[dict[str, Any]] = []
    audit = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "selected_by_window": {},
        "raw_candidate_count_by_window": {},
        "rejected_count_by_window": {},
        "scan_by_window": {},
        "contexts_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in _trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, contexts, scan = build_sec_periodic_report_absorption_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            sec_filing_events=event_rows,
            dates=dates,
            sector_entries=sector_map,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
        )
        selected, rejected = select_sec_periodic_report_absorption_paper_trades(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            config=cfg,
        )
        for trade in selected:
            trade["window"] = label
        all_trades.extend(selected)
        audit["selected_by_window"][label] = len(selected)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
        audit["contexts_by_window"][label] = contexts[:25]
    audit["total_selected"] = len(all_trades)
    audit["total_raw_candidates"] = sum(audit["raw_candidate_count_by_window"].values())
    return all_trades, audit


def build_sec_periodic_report_absorption_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    sec_filing_events: list[dict[str, Any]] | str | Path,
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    events_by_date_ticker, event_scan = _periodic_report_events_by_date_ticker(
        _normalise_event_source(sec_filing_events),
        cfg,
    )
    indices = {ticker: leader._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    entries_by_date = core_entries_by_date or {}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    form_distribution: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(dates),
        "periodic_report_days": 0,
        "periodic_report_tickers": 0,
        "days_with_raw_periodic_report_candidates": 0,
        "raw_periodic_report_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        **event_scan,
    }

    for signal_date in dates:
        event_map = events_by_date_ticker.get(signal_date) or {}
        if not event_map:
            continue
        scan["periodic_report_days"] += 1
        scan["periodic_report_tickers"] += len(event_map)
        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {str(entry.get("ticker") or "").upper() for entry in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(event_map.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_ticker(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
                config=cfg,
            )
            if row is None:
                continue
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)
            for event in events:
                form_distribution[str(event.get("form_type") or event.get("form_base") or "")] += 1
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_periodic_report_candidates"] += 1
        scan["raw_periodic_report_candidates"] += len(day_rows)
        top = day_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_form_types": top["candidate_periodic_report_form_types"],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )
    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    scan.update(
        {
            "rule_version": SOURCE_RULE_VERSION,
            "form_type_distribution": dict(sorted(form_distribution.items())),
            **_parameter_summary(cfg),
        }
    )
    return candidates, contexts, scan


def select_sec_periodic_report_absorption_signal_rows(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _select_candidates(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        existing_state=existing_state,
        config=config,
        create_trades=False,
    )


def select_sec_periodic_report_absorption_paper_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _select_candidates(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        existing_state=existing_state,
        config=config,
        create_trades=True,
    )


def replay_trade_from_candidate(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(rows_by_ticker)
    ticker = str(candidate.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    idx = leader._row_index(rows).get(str(candidate.get("date") or "")[:10])
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(cfg["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = leader._positive_float(rows[entry_idx].get("open"))
    exit_raw = leader._positive_float(rows[exit_idx].get("close"))
    if entry_raw is None or exit_raw is None:
        return None
    entry_price = apply_slippage(entry_raw, SLIPPAGE_BPS_ENTRY, "buy")
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    notional = float(cfg["paper_notional_usd"])
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(cfg["round_trip_cost_pct"])
    signal_date = str(candidate["date"])[:10]
    return {
        **deepcopy(candidate),
        "decision_id": _decision_id(candidate),
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "signal_date": signal_date,
        "entry_date": rows[entry_idx]["date"],
        "entry_raw_open": leader._round(entry_raw, 4),
        "entry_price": leader._round(entry_price, 4),
        "exit_date": rows[exit_idx]["date"],
        "exit_raw_close": leader._round(exit_raw, 4),
        "exit_price": leader._round(exit_price, 4),
        "hold_days": int(cfg["hold_days"]),
        "paper_notional_usd": notional,
        "notional_usd": notional,
        "pnl_pct_net": leader._round(pnl_pct_net, 6),
        "net_return_pct": leader._round(pnl_pct_net, 6),
        "pnl": leader._round(notional * pnl_pct_net, 2),
        "paper_status": "closed",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _normalise_event_source(source: list[dict[str, Any]] | str | Path | None) -> list[dict[str, Any]]:
    if source is None:
        return []
    if isinstance(source, list):
        return [row for row in source if isinstance(row, dict)]
    path = Path(source)
    if not path.exists():
        return []
    return load_sec_filing_event_rows(path)


def _periodic_report_events_by_date_ticker(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    accepted_forms = {str(item).upper() for item in config["accepted_form_types"]}
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    scan: Counter[str] = Counter()
    seen: set[str] = set()
    for row in rows:
        scan["sec_event_rows_loaded"] += 1
        ticker = str(row.get("ticker") or "").upper().strip()
        usable_date = leader._date10(row.get("usable_trade_date") or row.get("filing_date"))
        form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
        accession = str(row.get("accession_number") or f"{ticker}:{usable_date}:{form_type}")
        if accession in seen:
            scan["duplicate_accession_rows"] += 1
            continue
        seen.add(accession)
        if not ticker or not usable_date:
            scan["missing_ticker_or_usable_date"] += 1
            continue
        if form_type not in accepted_forms:
            scan["non_periodic_form_rejected"] += 1
            continue
        if row.get("is_amendment") is True:
            scan["amendment_rejected"] += 1
            continue
        if row.get("pit_safe_flag") is False:
            scan["pit_unsafe_rejected"] += 1
            continue
        event = {
            "ticker": ticker,
            "usable_trade_date": usable_date,
            "filing_date": leader._date10(row.get("filing_date")),
            "accepted_at": row.get("accepted_at"),
            "accession_number": row.get("accession_number"),
            "form_type": form_type,
            "form_base": row.get("form_base"),
            "size": leader._float_or_none(row.get("size")),
            "archive_url": row.get("archive_url"),
            "pit_safe_flag": row.get("pit_safe_flag"),
        }
        out.setdefault(usable_date, {}).setdefault(ticker, []).append(event)
        scan["periodic_report_events"] += 1
    return out, dict(scan)


def _candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    events: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in {"SPY", "QQQ"}:
        return None
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    qqq_rows = rows_by_ticker.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    row = rows[idx]
    close = leader._positive_float(row.get("close"))
    if close is None or close < float(config["min_price"]):
        return None
    signal_return = leader._daily_return(rows, idx)
    spy_return = leader._daily_return(spy_rows, spy_idx)
    qqq_return = leader._daily_return(qqq_rows, qqq_idx)
    if signal_return is None or spy_return is None or qqq_return is None:
        return None
    relative_vs_spy = signal_return - spy_return
    relative_vs_qqq = signal_return - qqq_return
    if signal_return < float(config["min_signal_return"]):
        return None
    if relative_vs_spy < float(config["min_relative_vs_spy"]):
        return None
    if relative_vs_qqq < float(config["min_relative_vs_qqq"]):
        return None
    close_location = leader._close_location(row)
    volume_ratio = leader._volume_ratio(rows, idx)
    avg_dollar_volume = leader._avg_dollar_volume(rows, idx)
    if close_location is None or close_location < float(config["min_close_location"]):
        return None
    if volume_ratio is None or volume_ratio < float(config["min_volume_ratio_20d"]):
        return None
    if volume_ratio > float(config["max_volume_ratio_20d"]):
        return None
    if avg_dollar_volume is None or avg_dollar_volume < float(config["min_avg_dollar_volume_20d"]):
        return None
    ret5 = leader._ret(rows, idx, 5)
    ret20 = leader._ret(rows, idx, 20)
    ret60 = leader._ret(rows, idx, 60)
    spy_ret20 = leader._ret(spy_rows, spy_idx, 20)
    spy_ret60 = leader._ret(spy_rows, spy_idx, 60)
    realized_vol20 = leader._realized_vol(rows, idx, 20)
    if None in (ret5, ret20, ret60, spy_ret20, spy_ret60, realized_vol20):
        return None
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    if ret5 < float(config["min_ret5"]) or ret5 > float(config["max_ret5"]):
        return None
    if ret20 > float(config["max_ret20"]):
        return None
    if ret20_excess_spy < float(config["min_ret20_excess_spy"]):
        return None
    if ret60_excess_spy < float(config["min_ret60_excess_spy"]):
        return None
    if realized_vol20 > float(config["max_realized_vol_20d"]):
        return None

    forms = sorted({str(event.get("form_type") or "") for event in events})
    event_score = _event_score(events)
    candidate_score = (
        event_score
        + relative_vs_spy * 6.0
        + ret20_excess_spy * 2.0
        + close_location * 0.35
        + min(volume_ratio, 2.5) * 0.10
    )
    sector_meta = sector_entries.get(ticker) or {}
    candidate = {
        "ticker": ticker,
        "date": signal_date,
        "signal_date": signal_date,
        "source": SLEEVE_NAME,
        "strategy": "sec_periodic_report_absorption_leadership_candidate_pool",
        "candidate_score": leader._round(candidate_score, 6),
        "candidate_periodic_report_score": leader._round(event_score, 6),
        "candidate_periodic_report_form_types": forms,
        "candidate_periodic_report_event_count": len(events),
        "candidate_periodic_report_accessions": [
            str(event.get("accession_number") or "") for event in events[:3]
        ],
        "candidate_signal_return": leader._round(signal_return, 6),
        "candidate_spy_return": leader._round(spy_return, 6),
        "candidate_qqq_return": leader._round(qqq_return, 6),
        "candidate_relative_vs_spy": leader._round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": leader._round(relative_vs_qqq, 6),
        "candidate_ret5": leader._round(ret5, 6),
        "candidate_ret20": leader._round(ret20, 6),
        "candidate_ret60": leader._round(ret60, 6),
        "candidate_spy_ret20": leader._round(spy_ret20, 6),
        "candidate_spy_ret60": leader._round(spy_ret60, 6),
        "candidate_ret20_excess_spy": leader._round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": leader._round(ret60_excess_spy, 6),
        "candidate_close_location": leader._round(close_location, 6),
        "candidate_avg_dollar_volume_20d": leader._round(avg_dollar_volume, 2),
        "candidate_volume_ratio_20d": leader._round(volume_ratio, 6),
        "candidate_realized_vol_20d": leader._round(realized_vol20, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "known_at": "sec_periodic_report_usable_date_and_signal_day_ohlcv_before_next_open_paper_entry",
        "uses_free_sec_filing_events": True,
        "uses_free_ohlcv": True,
        "uses_llm": False,
        "trade_enabled": False,
        "alters_orders": False,
    }
    candidate["decision_id"] = _decision_id(candidate)
    return candidate


def _select_candidates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None,
    config: dict[str, Any] | None,
    create_trades: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(rows_by_ticker)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    cooldown_until: dict[str, str] = {}
    for row in sorted(candidates, key=lambda item: (item["date"], *_candidate_sort_key(item))):
        signal_date = str(row["date"])[:10]
        ticker = str(row["ticker"]).upper()
        if str(cooldown_until.get(ticker) or "") > signal_date:
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        day_count = sum(1 for item in selected if str(item.get("date") or item.get("signal_date"))[:10] == signal_date)
        if day_count >= int(cfg["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_entry_slots"})
            continue
        if existing_state and leader._has_pending_open_or_closed_decision(
            existing_state,
            _decision_id(row),
        ):
            rejected.append({**row, "filter_reason": "duplicate_decision_id"})
            continue
        chosen: dict[str, Any] | None = row
        if create_trades:
            chosen = replay_trade_from_candidate(
                rows_by_ticker=rows_by_ticker,
                candidate=row,
                config=cfg,
            )
            if chosen is None:
                rejected.append({**row, "filter_reason": "missing_forward_entry_or_exit"})
                continue
        selected.append(chosen)
        cooldown_until[ticker] = _cooldown_until(rows_by_ticker, ticker, signal_date, int(cfg["same_ticker_cooldown_days"]))
    return selected, rejected


def _event_score(events: list[dict[str, Any]]) -> float:
    score = 0.0
    for event in events:
        form = str(event.get("form_type") or "").upper()
        size = leader._float_or_none(event.get("size")) or 0.0
        score += 1.20 if form == "10-Q" else 1.00
        if size >= 20_000_000:
            score += 0.25
        elif size >= 10_000_000:
            score += 0.10
    return score


def _cooldown_until(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
    days: int,
) -> str:
    rows = rows_by_ticker.get(ticker) or []
    idx = leader._row_index(rows).get(signal_date)
    if idx is None:
        return signal_date
    target = min(idx + max(days, 1), len(rows) - 1)
    return str(rows[target]["date"])


def _pending_entry_from_candidate(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(row)
    out.update(
        {
            "decision_id": _decision_id(row),
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "paper_notional_usd": float(config["paper_notional_usd"]),
            "notional_usd": float(config["paper_notional_usd"]),
            "entry_timing": "next_session_open",
            "hold_days": int(config["hold_days"]),
            "paper_status": "pending_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return out


def _snapshot_payload(
    state: dict[str, Any],
    *,
    as_of: str,
    candidates: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    scan: dict[str, Any],
    new_pending_entries: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    _normalise_state(state)
    closed_positions = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    realized = round(sum(float(row.get("pnl") or 0.0) for row in closed_positions), 2)
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(config.get("paper_enabled", True)),
        "trade_enabled": False,
        "candidate_count": len(selected_rows),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(new_pending_entries),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(state.get("pending_entries") or []),
        "open_position_count": len(state.get("open_positions") or []),
        "closed_position_count": len(closed_positions),
        "realized_pnl_to_date": realized,
        "unrealized_pnl": leader._unrealized_pnl(
            state.get("open_positions") or [],
            rows_by_ticker,
            as_of,
        ),
        "candidates": selected_rows,
        "raw_candidates": candidates[:50],
        "rejected_candidates": rejected[:50],
        "new_pending_entries": new_pending_entries,
        "filled_today": filled_today,
        "closed_today": closed_today,
        "sec_periodic_report_absorption_context": {
            "contexts": contexts[:25],
            "scan": scan,
        },
        "candidate_universe": _candidate_universe_summary(candidate_universe, rows_by_ticker),
        "forward_paper_gate": _forward_paper_gate(closed_positions, config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_replacement_value_no_orders",
    }


def _resolve_sector_entries(
    *,
    sector_entries: dict[str, dict[str, Any]] | None,
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    if sector_entries:
        return {str(ticker).upper(): dict(meta) for ticker, meta in sector_entries.items()}
    if isinstance(candidate_universe, dict):
        entries = candidate_universe.get("sector_entries")
        if isinstance(entries, dict):
            return {str(ticker).upper(): dict(meta) for ticker, meta in entries.items()}
        tickers = candidate_universe.get("tickers") or []
    elif isinstance(candidate_universe, list):
        tickers = candidate_universe
    else:
        tickers = rows_by_ticker.keys()
    out: dict[str, dict[str, Any]] = {}
    cache = leader._sector_cache()
    for ticker in tickers:
        symbol = str(ticker).upper()
        if symbol not in rows_by_ticker:
            continue
        lookup = cache.get(symbol) or {}
        sector = lookup.get("sector")
        industry = lookup.get("industry")
        status = lookup.get("status") or lookup.get("sector_coverage_status") or ("ok" if sector else "missing")
        if sector and status == "ok":
            out[symbol] = {
                "sector": sector,
                "industry": industry,
                "sector_coverage_status": status,
            }
    return out


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_days", [])


def _skip_payload(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:SKIP:{reason}",
        "date": as_of,
        "reason": reason,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _append_skip_once(state: dict[str, Any], row: dict[str, Any]) -> None:
    existing = {
        str(item.get("decision_id") or "")
        for item in state.get("skipped_days") or []
        if isinstance(item, dict)
    }
    if row["decision_id"] not in existing:
        state["skipped_days"].append(row)


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_periodic_report_score") or 0.0),
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("candidate_ret20_excess_spy") or 0.0),
        -float(row.get("candidate_close_location") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("sector") or ""),
        str(row.get("ticker") or ""),
    )


def _decision_id(row: dict[str, Any]) -> str:
    signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    return f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}"


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})


def _candidate_universe_summary(
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(candidate_universe, dict):
        return {
            "status": candidate_universe.get("status") or "provided",
            "ticker_count": len(candidate_universe.get("tickers") or rows_by_ticker),
            "loaded_ohlcv_ticker_count": len(rows_by_ticker),
        }
    if isinstance(candidate_universe, list):
        return {
            "status": "provided_list",
            "ticker_count": len(candidate_universe),
            "loaded_ohlcv_ticker_count": len(rows_by_ticker),
        }
    return {
        "status": "ohlcv_dict",
        "ticker_count": len(rows_by_ticker),
        "loaded_ohlcv_ticker_count": len(rows_by_ticker),
    }


def _forward_paper_gate(closed_positions: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in closed_positions if leader._float_or_none(row.get("pnl")) is not None]
    pnl = round(sum(float(row.get("pnl") or 0.0) for row in rows), 2)
    wins = sum(1 for row in rows if float(row.get("pnl") or 0.0) > 0)
    win_rate = wins / len(rows) if rows else None
    single_share, hhi = leader._positive_concentration(rows)
    checks = {
        "min_closed_trades": len(rows) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": pnl > 0 if config["forward_gate_positive_net_pnl"] else True,
        "min_win_rate": win_rate is not None and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_positive_hhi": hhi is not None and hhi <= float(config["forward_gate_max_positive_hhi"]),
    }
    reasons = [key for key, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "metrics": {
            "closed_trades": len(rows),
            "realized_pnl": pnl,
            "win_rate": leader._round(win_rate, 6),
            "single_ticker_positive_share": single_share,
            "positive_pnl_hhi": hhi,
        },
        "checks": checks,
    }


def _parameter_summary(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "paper_notional_usd",
        "daily_entry_slots",
        "hold_days",
        "same_ticker_cooldown_days",
        "accepted_form_types",
        "min_price",
        "min_avg_dollar_volume_20d",
        "min_signal_return",
        "min_relative_vs_spy",
        "min_relative_vs_qqq",
        "min_close_location",
        "min_volume_ratio_20d",
        "max_volume_ratio_20d",
        "min_ret5",
        "max_ret5",
        "max_ret20",
        "min_ret20_excess_spy",
        "min_ret60_excess_spy",
        "max_realized_vol_20d",
    ]
    return {key: config[key] for key in keys}


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "paper attribution module only; core trading policy unchanged",
        "backtester_adapter_changed": True,
        "run_adapter_changed": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": True,
        "trade_enabled": False,
        "alters_orders": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_free_sec_filing_events": True,
        "uses_free_ohlcv": True,
        "live_ready": False,
    }
