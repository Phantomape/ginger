"""Default-off distribution-day absorption leadership paper sleeve.

Shared helper for the positive exp-20260611-006 replay lead. After recent
SPY/QQQ high-volume distribution days, it admits one liquid sector-known stock
that absorbs the pressure, reclaims a short prior high, closes strong, and
leads SPY/QQQ.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import broad_market_sector_map
    import macro_relief_leadership_paper_sleeve as leader
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import broad_market_sector_map
    from quant import macro_relief_leadership_paper_sleeve as leader
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage


SLEEVE_NAME = "DISTRIBUTION_DAY_ABSORPTION_LEADERSHIP_PAPER"
RULE_VERSION = "distribution_day_absorption_leadership_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "distribution_day_absorption_leadership_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "distribution_day_absorption_leadership" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "distribution_day_absorption_leadership"
    / "snapshots.jsonl"
)

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
    "CPER",
    "DIA",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "VIXM",
    "VIXY",
    "VXX",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
}

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
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "pressure_lookback_days": 7,
    "min_combined_distribution_events": 2,
    "max_index_signal_return": 0.020,
    "min_index_signal_return": -0.006,
    "max_recent_spy_qqq_ret5": 0.018,
    "min_recent_spy_qqq_ret5": -0.105,
    "max_index_close_location_on_distribution": 0.58,
    "max_index_distribution_return": -0.004,
    "min_index_distribution_volume_ratio": 1.04,
    "prior_high_lookback_days": 10,
    "min_candidate_signal_return": 0.005,
    "min_candidate_relative_vs_spy": 0.018,
    "min_candidate_relative_vs_qqq": 0.020,
    "min_candidate_close_location": 0.72,
    "min_candidate_volume_ratio_20d": 0.95,
    "min_candidate_ret5": -0.020,
    "max_candidate_ret5": 0.120,
    "max_candidate_ret20": 0.320,
    "min_candidate_ret20_excess_spy": 0.035,
    "min_candidate_ret60_excess_spy": -0.020,
    "min_candidate_reclaim_vs_10d_high": -0.002,
    "max_candidate_reclaim_vs_10d_high": 0.060,
    "max_candidate_realized_vol_20": 0.085,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_distribution_day_absorption_leadership_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_distribution_day_absorption_leadership_snapshot(
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
        "distribution_day_absorption_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_distribution_day_absorption_leadership_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_distribution_day_absorption_leadership_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_distribution_day_absorption_leadership_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_distribution_day_absorption_leadership_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(leader._safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_distribution_day_absorption_leadership_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(leader._safe(snapshot), sort_keys=True) + "\n")


def build_distribution_day_absorption_leadership_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
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
        else load_distribution_day_absorption_leadership_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_distribution_day_absorption_leadership_snapshot(
            as_of_date,
            "missing_ohlcv",
        )
    if "SPY" not in rows_by_ticker or "QQQ" not in rows_by_ticker:
        return empty_distribution_day_absorption_leadership_snapshot(
            as_of_date,
            "missing_spy_or_qqq_ohlcv",
        )

    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    if not sector_map:
        return empty_distribution_day_absorption_leadership_snapshot(
            as_of_date,
            "missing_sector_entries",
        )

    filled_today = leader._fill_pending_entries(
        working_state,
        rows_by_ticker,
        as_of_date,
        cfg,
    )
    closed_today = leader._advance_open_positions(
        working_state,
        rows_by_ticker,
        as_of_date,
        cfg,
    )
    candidates, contexts, scan = build_distribution_day_absorption_leadership_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        sector_entries=sector_map,
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
    )
    selected_rows, rejected = select_distribution_day_absorption_leadership_signal_rows(
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
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_distribution_pressure_context"))
    elif not selected_rows and contexts and not candidates:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_absorption_leadership_candidate"))

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
        save_distribution_day_absorption_leadership_state(working_state, state_path)
        append_distribution_day_absorption_leadership_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_distribution_day_absorption_leadership_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
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
        candidates, contexts, scan = build_distribution_day_absorption_leadership_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_map,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
        )
        selected, rejected = select_distribution_day_absorption_leadership_paper_trades(
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


def build_distribution_day_absorption_leadership_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: leader._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    candidate_tickers: set[str] = set()
    entries_by_date = core_entries_by_date or {}
    scan = {
        "scanned_trading_days": len(dates),
        "pressure_days": 0,
        "non_pressure_days": 0,
        "missing_context_days": 0,
        "days_with_raw_absorption_candidates": 0,
        "raw_absorption_candidates": 0,
        "rule_version": SOURCE_RULE_VERSION,
    }
    for signal_date in dates:
        context = _distribution_pressure_context(
            rows_by_ticker=rows_by_ticker,
            indices=indices,
            signal_date=signal_date,
            config=cfg,
        )
        if context is None:
            scan["missing_context_days"] += 1
            continue
        if not context["passed"]:
            scan["non_pressure_days"] += 1
            continue
        scan["pressure_days"] += 1
        contexts.append(context)
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = _candidate_for_ticker(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
                config=cfg,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                str(trade.get("ticker") or "").upper() == ticker for trade in ab_entries
            )
            day_rows.append(row)
            candidate_tickers.add(ticker)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_absorption_candidates"] += 1
        scan["raw_absorption_candidates"] += len(day_rows)
    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    scan.update(
        {
            "unique_candidate_tickers": len(candidate_tickers),
            **_parameter_summary(cfg),
        }
    )
    return candidates, contexts, scan


def select_distribution_day_absorption_leadership_signal_rows(
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


def select_distribution_day_absorption_leadership_paper_trades(
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
        "paper_notional_usd": leader._round(notional, 2),
        "notional_usd": leader._round(notional, 2),
        "pnl_pct_net": leader._round(pnl_pct_net, 6),
        "net_return_pct": leader._round(pnl_pct_net, 6),
        "pnl": leader._round(notional * pnl_pct_net, 2),
        "paper_status": "closed",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _select_candidates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None,
    config: dict[str, Any] | None,
    create_trades: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    all_dates = _trading_dates(rows_by_ticker)
    date_pos = {day: idx for idx, day in enumerate(all_dates)}
    next_allowed_pos_by_ticker = _state_cooldown_map(
        existing_state=existing_state,
        date_pos=date_pos,
        config=cfg,
    )
    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            rejected.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= int(cfg["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        if create_trades:
            trade = replay_trade_from_candidate(
                rows_by_ticker=rows_by_ticker,
                candidate=row,
                config=cfg,
            )
            if trade is None:
                rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
                continue
            selected.append(trade)
        else:
            selected.append(
                {
                    **deepcopy(row),
                    "decision_id": _decision_id(row),
                    "sleeve": SLEEVE_NAME,
                    "rule_version": RULE_VERSION,
                    "source_rule_version": SOURCE_RULE_VERSION,
                    "signal_date": signal_date,
                    "paper_status": "candidate",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    return selected, rejected


def _distribution_pressure_context(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    spy_rows = rows_by_ticker.get("SPY") or []
    qqq_rows = rows_by_ticker.get("QQQ") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None or spy_idx < 60 or qqq_idx < 60:
        return None

    spy_ret5 = leader._ret(spy_rows, spy_idx, 5)
    qqq_ret5 = leader._ret(qqq_rows, qqq_idx, 5)
    spy_signal = leader._daily_return(spy_rows, spy_idx)
    qqq_signal = leader._daily_return(qqq_rows, qqq_idx)
    if None in (spy_ret5, qqq_ret5, spy_signal, qqq_signal):
        return None

    spy_events = _distribution_events(spy_rows, spy_idx, config)
    qqq_events = _distribution_events(qqq_rows, qqq_idx, config)
    combined_count = len(spy_events) + len(qqq_events)
    passed = (
        combined_count >= int(config["min_combined_distribution_events"])
        and float(config["min_recent_spy_qqq_ret5"])
        <= min(float(spy_ret5), float(qqq_ret5))
        and max(float(spy_ret5), float(qqq_ret5))
        <= float(config["max_recent_spy_qqq_ret5"])
        and float(config["min_index_signal_return"])
        <= float(spy_signal)
        <= float(config["max_index_signal_return"])
        and float(config["min_index_signal_return"])
        <= float(qqq_signal)
        <= float(config["max_index_signal_return"])
    )
    return {
        "date": signal_date,
        "passed": passed,
        "reason": (
            "distribution_pressure_absorption_window_passed"
            if passed
            else "distribution_pressure_context_failed"
        ),
        "lookback_days": int(config["pressure_lookback_days"]),
        "combined_distribution_event_count": combined_count,
        "spy_distribution_event_count": len(spy_events),
        "qqq_distribution_event_count": len(qqq_events),
        "spy_distribution_events": spy_events,
        "qqq_distribution_events": qqq_events,
        "spy_ret5": leader._round(float(spy_ret5), 6),
        "qqq_ret5": leader._round(float(qqq_ret5), 6),
        "spy_signal_day_return": leader._round(float(spy_signal), 6),
        "qqq_signal_day_return": leader._round(float(qqq_signal), 6),
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "rule_version": SOURCE_RULE_VERSION,
    }


def _distribution_events(
    rows: list[dict[str, Any]],
    idx: int,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    start = max(20, idx - int(config["pressure_lookback_days"]))
    for pos in range(start, idx):
        signal_return = leader._daily_return(rows, pos)
        volume_ratio = leader._volume_ratio(rows, pos)
        close_location = leader._close_location(rows[pos])
        if signal_return is None or volume_ratio is None or close_location is None:
            continue
        if (
            signal_return <= float(config["max_index_distribution_return"])
            and volume_ratio >= float(config["min_index_distribution_volume_ratio"])
            and close_location <= float(config["max_index_close_location_on_distribution"])
        ):
            events.append(
                {
                    "date": rows[pos]["date"],
                    "return": leader._round(signal_return, 6),
                    "volume_ratio_20d": leader._round(volume_ratio, 6),
                    "close_location": leader._round(close_location, 6),
                }
            )
    return events


def _candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    qqq_rows = rows_by_ticker.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or qqq_idx < 60:
        return None
    close = leader._positive_float(rows[idx].get("close"))
    if close is None or close < float(config["min_price"]):
        return None
    adv20 = leader._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None

    prior_high = _prior_high(rows, idx, int(config["prior_high_lookback_days"]))
    signal_return = leader._daily_return(rows, idx)
    spy_signal = leader._daily_return(spy_rows, spy_idx)
    qqq_signal = leader._daily_return(qqq_rows, qqq_idx)
    close_location = leader._close_location(rows[idx])
    volume_ratio = leader._volume_ratio(rows, idx)
    ret5 = leader._ret(rows, idx, 5)
    ret20 = leader._ret(rows, idx, 20)
    ret60 = leader._ret(rows, idx, 60)
    spy_ret20 = leader._ret(spy_rows, spy_idx, 20)
    spy_ret60 = leader._ret(spy_rows, spy_idx, 60)
    realized_vol = leader._realized_vol(rows, idx, 20)
    required = [
        prior_high,
        signal_return,
        spy_signal,
        qqq_signal,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol,
    ]
    if any(value is None for value in required):
        return None
    assert prior_high is not None
    assert signal_return is not None
    assert spy_signal is not None
    assert qqq_signal is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol is not None

    reclaim_vs_high = (float(close) / float(prior_high)) - 1.0
    relative_vs_spy = float(signal_return) - float(spy_signal)
    relative_vs_qqq = float(signal_return) - float(qqq_signal)
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)

    if signal_return < float(config["min_candidate_signal_return"]):
        return None
    if relative_vs_spy < float(config["min_candidate_relative_vs_spy"]):
        return None
    if relative_vs_qqq < float(config["min_candidate_relative_vs_qqq"]):
        return None
    if close_location < float(config["min_candidate_close_location"]):
        return None
    if volume_ratio < float(config["min_candidate_volume_ratio_20d"]):
        return None
    if (
        ret5 < float(config["min_candidate_ret5"])
        or ret5 > float(config["max_candidate_ret5"])
    ):
        return None
    if ret20 > float(config["max_candidate_ret20"]):
        return None
    if ret20_excess_spy < float(config["min_candidate_ret20_excess_spy"]):
        return None
    if ret60_excess_spy < float(config["min_candidate_ret60_excess_spy"]):
        return None
    if reclaim_vs_high < float(config["min_candidate_reclaim_vs_10d_high"]):
        return None
    if reclaim_vs_high > float(config["max_candidate_reclaim_vs_10d_high"]):
        return None
    if realized_vol > float(config["max_candidate_realized_vol_20"]):
        return None

    sector_meta = sector_entries[ticker]
    score = (
        2.2 * relative_vs_spy
        + 2.0 * relative_vs_qqq
        + 0.85 * ret20_excess_spy
        + 0.30 * ret60_excess_spy
        + 0.45 * close_location
        + 0.25 * min(volume_ratio, 3.0)
        + 0.20 * min(max(reclaim_vs_high, 0.0), 0.06)
        + 0.05 * math.log10(max(float(adv20), 1.0) / 1_000_000.0)
        + 0.05 * context["combined_distribution_event_count"]
        - 0.65 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": SLEEVE_NAME,
        "candidate_score": leader._round(score, 6),
        "candidate_signal_day_return": leader._round(float(signal_return), 6),
        "candidate_relative_vs_spy": leader._round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": leader._round(relative_vs_qqq, 6),
        "candidate_ret5": leader._round(float(ret5), 6),
        "candidate_ret20": leader._round(float(ret20), 6),
        "candidate_ret60": leader._round(float(ret60), 6),
        "candidate_spy_ret20": leader._round(float(spy_ret20), 6),
        "candidate_ret20_excess_spy": leader._round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": leader._round(ret60_excess_spy, 6),
        "candidate_close_location": leader._round(float(close_location), 6),
        "candidate_avg_dollar_volume_20d": leader._round(float(adv20), 2),
        "candidate_volume_ratio_20d": leader._round(float(volume_ratio), 6),
        "candidate_realized_vol_20d": leader._round(float(realized_vol), 6),
        "candidate_prior_10d_high": leader._round(float(prior_high), 6),
        "candidate_reclaim_vs_10d_high": leader._round(reclaim_vs_high, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status")
        or sector_meta.get("status"),
        "pressure_context": context,
        "rule_version": SOURCE_RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "alters_orders": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _prior_high(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    highs = [leader._positive_float(row.get("high")) for row in rows[idx - lookback : idx]]
    if any(value is None for value in highs):
        return None
    valid = [float(value) for value in highs if value is not None]
    return max(valid) if valid else None


def _pending_entry_from_candidate(candidate: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(candidate)
    out.update(
        {
            "decision_id": _decision_id(candidate),
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "signal_date": str(candidate.get("date") or candidate.get("signal_date") or "")[:10],
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
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    pending = [row for row in state.get("pending_entries") or [] if isinstance(row, dict)]
    open_positions = [row for row in state.get("open_positions") or [] if isinstance(row, dict)]
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
        "trade_enabled_reason": "default_off_until_forward_gate_and_trade_adapter_pass",
        "candidate_count": len(selected_rows),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "candidate": selected_rows[0] if selected_rows else None,
        "candidates": selected_rows,
        "rejected_candidates": rejected[:50],
        "distribution_day_absorption_context": {
            **scan,
            "read_only": True,
            "trade_enabled": False,
            "alters_orders": False,
            "context_samples": contexts[:10],
        },
        "context_scan": scan,
        "candidate_universe": _candidate_universe_summary(candidate_universe, rows_by_ticker),
        "new_pending_entries": new_pending_entries,
        "new_pending_count": len(new_pending_entries),
        "pending_entries": pending,
        "pending_count": len(pending),
        "filled_today": filled_today,
        "filled_count": len(filled_today),
        "opened_positions_this_run": filled_today,
        "open_positions": open_positions,
        "open_position_count": len(open_positions),
        "closed_today": closed_today,
        "closed_positions_today": closed_today,
        "closed_positions_this_run": closed_today,
        "skipped_entries_this_run": [],
        "closed_count_today": len(closed_today),
        "closed_positions": closed,
        "closed_position_count": len(closed),
        "realized_pnl_to_date": leader._round(
            sum(leader._float_or_none(row.get("pnl")) or 0.0 for row in closed),
            2,
        ),
        "unrealized_pnl": leader._unrealized_pnl(open_positions, rows_by_ticker, as_of),
        "forward_paper_gate": leader._forward_paper_gate(closed, config),
        "parameters": _parameter_summary(config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _resolve_sector_entries(
    *,
    sector_entries: dict[str, dict[str, Any]] | None,
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    if sector_entries:
        raw_entries = sector_entries
    elif isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("records"), dict):
        raw_entries = candidate_universe["records"]
    elif isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("entries"), dict):
        raw_entries = candidate_universe["entries"]
    else:
        cache = broad_market_sector_map.load_cache()
        raw_entries = cache.get("entries", {}) if isinstance(cache, dict) else {}

    allowed = (
        {str(ticker).upper() for ticker in candidate_universe}
        if isinstance(candidate_universe, list)
        else set(rows_by_ticker)
    )
    if isinstance(candidate_universe, dict) and candidate_universe.get("tickers"):
        allowed = {str(ticker).upper() for ticker in candidate_universe.get("tickers") or []}

    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in raw_entries.items():
        ticker_u = str(ticker).upper()
        if ticker_u in EXCLUDED_TICKERS or "." in ticker_u or "-" in ticker_u:
            continue
        if ticker_u not in rows_by_ticker or ticker_u not in allowed:
            continue
        if not isinstance(meta, dict):
            continue
        sector = meta.get("sector") or meta.get("gics_sector")
        status = meta.get("status") or meta.get("sector_coverage_status") or "ok"
        if not sector or status != "ok":
            continue
        out[ticker_u] = {
            "sector": sector,
            "industry": meta.get("industry"),
            "sector_coverage_status": status,
        }
    return out


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_days"):
        if not isinstance(state.get(key), list):
            state[key] = []


def _state_cooldown_map(
    *,
    existing_state: dict[str, Any] | None,
    date_pos: dict[str, int],
    config: dict[str, Any],
) -> dict[str, int]:
    next_allowed_pos_by_ticker: dict[str, int] = {}
    if not existing_state:
        return next_allowed_pos_by_ticker
    for bucket in ("pending_entries", "open_positions"):
        for row in existing_state.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            date_value = str(row.get("signal_date") or row.get("date") or "")[:10]
            pos = date_pos.get(date_value)
            if ticker and pos is not None:
                next_allowed_pos_by_ticker[ticker] = max(
                    next_allowed_pos_by_ticker.get(ticker, -1),
                    pos + int(config["same_ticker_cooldown_days"]),
                )
    return next_allowed_pos_by_ticker


def _append_skip_once(state: dict[str, Any], row: dict[str, Any]) -> None:
    existing = {
        str(item.get("decision_id") or "")
        for item in state.get("skipped_days") or []
        if isinstance(item, dict)
    }
    if row["decision_id"] not in existing:
        state["skipped_days"].append(row)


def _skip_payload(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:SKIP:{reason}",
        "date": as_of,
        "reason": reason,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _decision_id(row: dict[str, Any]) -> str:
    signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    return f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}"


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("candidate_ret20_excess_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("sector") or ""),
        str(row.get("ticker") or ""),
    )


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})


def _candidate_universe_summary(
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(candidate_universe, dict):
        count = len(candidate_universe.get("tickers") or candidate_universe.get("records") or rows_by_ticker)
        status = candidate_universe.get("status") or "provided"
    elif isinstance(candidate_universe, list):
        count = len(candidate_universe)
        status = "provided_ticker_list"
    else:
        count = len(rows_by_ticker)
        status = "ohlcv_dict_or_sector_cache"
    return {
        "status": status,
        "ticker_count": count,
        "loaded_ohlcv_ticker_count": len(rows_by_ticker),
    }


def _parameter_summary(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "paper_notional_usd",
        "daily_entry_slots",
        "hold_days",
        "same_ticker_cooldown_days",
        "min_price",
        "min_avg_dollar_volume_20d",
        "pressure_lookback_days",
        "min_combined_distribution_events",
        "max_index_signal_return",
        "min_index_signal_return",
        "max_recent_spy_qqq_ret5",
        "min_recent_spy_qqq_ret5",
        "max_index_close_location_on_distribution",
        "max_index_distribution_return",
        "min_index_distribution_volume_ratio",
        "prior_high_lookback_days",
        "min_candidate_signal_return",
        "min_candidate_relative_vs_spy",
        "min_candidate_relative_vs_qqq",
        "min_candidate_close_location",
        "min_candidate_volume_ratio_20d",
        "min_candidate_ret5",
        "max_candidate_ret5",
        "max_candidate_ret20",
        "min_candidate_ret20_excess_spy",
        "min_candidate_ret60_excess_spy",
        "min_candidate_reclaim_vs_10d_high",
        "max_candidate_reclaim_vs_10d_high",
        "max_candidate_realized_vol_20",
    ]
    return {key: config[key] for key in keys}


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def prep_and_build_distribution_day_absorption_leadership_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict,
    broad_market_candidate_universe: dict,
    spy_ohlcv=None,
    ohlcv_dict=None,
    cached_ohlcv_fn=None,
    core_entries=None,
):
    if not broad_market_candidate_universe.get("tickers"):
        return empty_distribution_day_absorption_leadership_snapshot(
            as_of, "broad_market_candidate_universe_unavailable")
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    if "QQQ" not in ohlcv:
        ohlcv["QQQ"] = (ohlcv_dict or {}).get("QQQ") or (cached_ohlcv_fn("QQQ") if cached_ohlcv_fn else None)
    return build_distribution_day_absorption_leadership_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv,
        candidate_universe=broad_market_candidate_universe,
        core_entries=core_entries,
    )


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
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_free_ohlcv_only": True,
        "adapter_status": "shared_default_off_paper_helper",
        "scope": "default_off_distribution_day_absorption_leadership_paper_attribution",
    }
