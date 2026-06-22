"""Default-off Moomoo daily short-volume activity paper sleeve.

Moomoo daily short-volume rows are treated as activity-only sell-pressure
context, not as FINRA short-interest positioning. The signal is known after the
activity date close and maps explicitly to the next tradable session for paper
entry.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage


SLEEVE_NAME = "MOOMOO_DAILY_SHORT_VOLUME_ACTIVITY_PAPER"
RULE_VERSION = "moomoo_daily_short_volume_activity_absorption_candidate_pool_v1"
SOURCE_RULE_VERSION = "moomoo_daily_short_volume_activity_archive_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_ACTIVITY_ROWS_PATH = DATA_ROOT / "non_ohlcv" / "moomoo_daily_short_volume" / "rows.jsonl"
DEFAULT_STATE_PATH = DATA_ROOT / "paper_sleeves" / "moomoo_daily_short_volume" / "state.json"
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "moomoo_daily_short_volume" / "snapshots.jsonl"
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
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "activity_lookback_rows": 60,
    "min_prior_activity_rows": 40,
    "min_activity_ratio": 0.12,
    "min_activity_ratio_vs_median": 1.35,
    "min_activity_volume": 1_000_000,
    "min_signal_return": 0.0,
    "min_signal_return_vs_spy": 0.0,
    "min_close_location": 0.55,
    "min_ret20_excess_spy": -0.02,
    "max_ret5": 0.14,
    "max_realized_vol_20d": 0.12,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_moomoo_daily_short_volume_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_moomoo_daily_short_volume_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "raw_candidate_count": 0,
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "activity_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_moomoo_daily_short_volume_state(path: Path | str = DEFAULT_STATE_PATH) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_moomoo_daily_short_volume_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_moomoo_daily_short_volume_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_moomoo_daily_short_volume_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_moomoo_daily_short_volume_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def load_moomoo_daily_short_volume_activity_rows(
    path: Path | str = DEFAULT_ACTIVITY_ROWS_PATH,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    activity_path = Path(path)
    if not activity_path.exists():
        return rows
    with activity_path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ticker = str(row.get("ticker") or "").upper()
            activity_date = _date10(row.get("activity_date"))
            ratio = _float(row.get("short_volume_ratio"))
            if not ticker or not activity_date or ratio is None:
                continue
            rows.append({**row, "ticker": ticker, "activity_date": activity_date})
    rows.sort(key=lambda row: (row["ticker"], row["activity_date"]))
    return rows


def build_moomoo_daily_short_volume_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    activity_rows: list[dict[str, Any]] | None = None,
    core_entries: list[dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    working_state = deepcopy(
        state if state is not None else load_moomoo_daily_short_volume_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_moomoo_daily_short_volume_snapshot(as_of_date, "missing_ohlcv")
    if "SPY" not in rows_by_ticker:
        return empty_moomoo_daily_short_volume_snapshot(as_of_date, "missing_spy_ohlcv")
    rows = activity_rows if activity_rows is not None else load_moomoo_daily_short_volume_activity_rows()
    if not rows:
        return empty_moomoo_daily_short_volume_snapshot(as_of_date, "missing_activity_rows")

    candidates, scan = build_moomoo_daily_short_volume_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        activity_rows=rows,
        dates=[as_of_date],
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
    )
    selected, rejected = select_moomoo_daily_short_volume_signal_rows(
        candidates=candidates,
        state=working_state,
        config=cfg,
    )
    pending_entries = []
    for row in selected:
        pending = {
            **row,
            "status": "pending_entry",
            "paper_notional_usd": cfg["paper_notional_usd"],
            "created_at": utc_now_iso(),
        }
        pending_entries.append(pending)
        working_state["pending_entries"].append(pending)
    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": bool(cfg["enabled"]),
        "paper_enabled": bool(cfg["paper_enabled"]),
        "trade_enabled": False,
        "candidate_count": len(selected),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(pending_entries),
        "pending_count": len(working_state["pending_entries"]),
        "open_position_count": len(working_state["open_positions"]),
        "closed_position_count": len(working_state["closed_positions"]),
        "realized_pnl_to_date": round(
            sum(float(row.get("pnl") or 0.0) for row in working_state["closed_positions"]),
            2,
        ),
        "unrealized_pnl": 0.0,
        "candidates": selected,
        "rejected_candidates": rejected[:50],
        "pending_entries_added": pending_entries,
        "activity_context": scan,
        "forward_paper_gate": _forward_paper_gate(working_state, cfg),
        "production_impact": _production_impact(),
    }
    if persist:
        save_moomoo_daily_short_volume_state(working_state, state_path)
        append_moomoo_daily_short_volume_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_moomoo_daily_short_volume_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    activity_rows: list[dict[str, Any]] | None = None,
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    windows: dict[str, dict[str, str]],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    rows = activity_rows if activity_rows is not None else load_moomoo_daily_short_volume_activity_rows()
    all_trades: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "selected_by_window": {},
        "raw_candidate_count_by_window": {},
        "rejected_count_by_window": {},
        "scan_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in _trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, scan = build_moomoo_daily_short_volume_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            activity_rows=rows,
            dates=dates,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
        )
        selected, rejected = select_moomoo_daily_short_volume_paper_trades(
            ohlcv_by_ticker=rows_by_ticker,
            candidates=candidates,
            state=empty_moomoo_daily_short_volume_state(),
            config=cfg,
        )
        window_trades = [{**row, "window": label} for row in selected]
        all_trades.extend(window_trades)
        audit["selected_by_window"][label] = len(window_trades)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
    return all_trades, _safe(audit)


def build_moomoo_daily_short_volume_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    activity_rows: list[dict[str, Any]],
    dates: list[str],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    activity_by_ticker = _activity_by_ticker(activity_rows)
    indices = {ticker: _row_index(rows) for ticker, rows in rows_by_ticker.items()}
    date_set = set(dates)
    candidates: list[dict[str, Any]] = []
    scan: Counter[str] = Counter()
    for ticker, act_rows in activity_by_ticker.items():
        if ticker not in rows_by_ticker:
            scan["activity_ticker_missing_ohlcv"] += 1
            continue
        for act_idx, activity in enumerate(act_rows):
            signal_date = str(activity.get("activity_date") or "")[:10]
            if signal_date not in date_set:
                continue
            scan["activity_rows_in_dates"] += 1
            row = _candidate_from_activity(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                activity_by_ticker=activity_by_ticker,
                ticker=ticker,
                activity_idx=act_idx,
                config=cfg,
            )
            if row is None:
                scan["activity_rows_rejected_by_rule"] += 1
                continue
            core_entries = (core_entries_by_date or {}).get(signal_date, [])
            row["same_day_core_entry_count"] = len(core_entries)
            row["same_day_core_overlap"] = bool(core_entries)
            row["same_ticker_core_overlap"] = any(
                str(entry.get("ticker") or "").upper() == ticker for entry in core_entries
            )
            candidates.append(row)
            scan["qualified_candidate_rows"] += 1
    candidates.sort(key=_candidate_sort_key)
    scan["candidate_signal_days"] = len({row["date"] for row in candidates})
    scan["candidate_tickers"] = len({row["ticker"] for row in candidates})
    scan["archive_tickers"] = len(activity_by_ticker)
    scan["params"] = {
        key: cfg[key]
        for key in [
            "activity_lookback_rows",
            "min_prior_activity_rows",
            "min_activity_ratio",
            "min_activity_ratio_vs_median",
            "min_signal_return",
            "min_signal_return_vs_spy",
            "daily_entry_slots",
            "hold_days",
            "same_ticker_cooldown_days",
        ]
    }
    return candidates, dict(scan)


def select_moomoo_daily_short_volume_signal_rows(
    *,
    candidates: list[dict[str, Any]],
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_signal_dates: Counter[str] = Counter()
    active_tickers = {
        str(row.get("ticker") or "").upper()
        for row in list(state.get("pending_entries") or []) + list(state.get("open_positions") or [])
    }
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        if row.get("same_ticker_core_overlap"):
            rejected.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if ticker in active_tickers:
            rejected.append({**row, "filter_reason": "already_active_or_pending"})
            continue
        if used_signal_dates[signal_date] >= int(cfg["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        selected.append(row)
        used_signal_dates[signal_date] += 1
        active_tickers.add(ticker)
    return selected, rejected


def select_moomoo_daily_short_volume_paper_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    candidates: list[dict[str, Any]],
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_signal_dates: Counter[str] = Counter()
    dates = _trading_dates(rows_by_ticker)
    date_pos = {day: idx for idx, day in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    active_tickers = {
        str(row.get("ticker") or "").upper()
        for row in list(state.get("pending_entries") or []) + list(state.get("open_positions") or [])
    }
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_core_overlap"):
            rejected.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if ticker in active_tickers:
            rejected.append({**row, "filter_reason": "already_active_or_pending"})
            continue
        if used_signal_dates[signal_date] >= int(cfg["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = paper_trade_from_candidate(rows_by_ticker, row, cfg)
        if trade is None:
            rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_signal_dates[signal_date] += 1
        active_tickers.add(ticker)
        next_allowed_pos_by_ticker[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    return selected, rejected


def paper_trade_from_candidate(
    ohlcv_by_ticker: dict[str, Any],
    candidate: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    ticker = str(candidate.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    idx = _row_index(rows).get(str(candidate.get("date") or ""))
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(cfg["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _value(rows[entry_idx], "Open")
    exit_raw = _value(rows[exit_idx], "Close")
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(cfg["round_trip_cost_pct"])
    pnl = float(cfg["paper_notional_usd"]) * pnl_pct_net
    return {
        **candidate,
        "signal_date": candidate.get("date"),
        "entry_date": _date(rows[entry_idx]),
        "exit_date": _date(rows[exit_idx]),
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": int(cfg["hold_days"]),
        "paper_notional_usd": float(cfg["paper_notional_usd"]),
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "entry_date_policy": "activity_date_next_trading_session_open",
        "target_price": _round(entry_price * 1.10, 4),
    }


def prep_and_build_moomoo_daily_short_volume_paper_sleeve_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict[str, Any],
    activity_rows: list[dict[str, Any]] | None = None,
    core_entries: list[dict[str, Any]] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    return build_moomoo_daily_short_volume_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=broad_market_ohlcv,
        activity_rows=activity_rows,
        core_entries=core_entries,
        persist=persist,
    )


def _candidate_from_activity(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    activity_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    activity_idx: int,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    activity = activity_by_ticker[ticker][activity_idx]
    signal_date = str(activity.get("activity_date") or "")[:10]
    prior_rows = activity_by_ticker[ticker][
        max(0, activity_idx - int(config["activity_lookback_rows"])) : activity_idx
    ]
    prior_ratios = [
        _float(row.get("short_volume_ratio"))
        for row in prior_rows
        if _float(row.get("short_volume_ratio")) is not None
    ]
    if len(prior_ratios) < int(config["min_prior_activity_rows"]):
        return None
    ratio = _float(activity.get("short_volume_ratio"))
    volume = _float(activity.get("volume"))
    total_short = _float(activity.get("total_shares_short"))
    if ratio is None or volume is None or total_short is None:
        return None
    prior_median = median(prior_ratios)
    if prior_median <= 0:
        return None
    ratio_vs_median = ratio / prior_median
    if ratio < float(config["min_activity_ratio"]):
        return None
    if ratio_vs_median < float(config["min_activity_ratio_vs_median"]):
        return None
    if volume < float(config["min_activity_volume"]):
        return None

    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 20 or spy_idx < 20:
        return None
    close = _value(rows[idx], "Close")
    if close is None or close < float(config["min_price"]):
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None
    signal_return = _daily_return(rows, idx)
    spy_return = _daily_return(spy_rows, spy_idx)
    if signal_return is None or spy_return is None:
        return None
    signal_vs_spy = signal_return - spy_return
    if signal_return < float(config["min_signal_return"]):
        return None
    if signal_vs_spy < float(config["min_signal_return_vs_spy"]):
        return None
    close_location = _close_location(rows[idx])
    if close_location is None or close_location < float(config["min_close_location"]):
        return None
    ret5 = _ret(rows, idx, 5)
    ret20 = _ret(rows, idx, 20)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    if ret5 is None or ret20 is None or spy_ret20 is None:
        return None
    if ret5 > float(config["max_ret5"]):
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < float(config["min_ret20_excess_spy"]):
        return None
    realized_vol = _realized_vol(rows, idx)
    if realized_vol is None or realized_vol > float(config["max_realized_vol_20d"]):
        return None
    entry_date = _next_usable_trade_date(rows, signal_date)
    if entry_date is None:
        return None

    score = (
        1.50 * min(ratio_vs_median, 4.0)
        + 1.00 * ratio
        + 1.35 * signal_vs_spy
        + 0.50 * signal_return
        + 0.30 * close_location
        + 0.12 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.40 * realized_vol
    )
    decision_id = f"{RULE_VERSION}:{signal_date}:{ticker}"
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": SLEEVE_NAME,
        "decision_id": decision_id,
        "candidate_score": _round(score, 6),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "activity_date": signal_date,
        "usable_trade_date": entry_date,
        "known_at": "after_activity_date_close_before_next_open_paper_entry",
        "activity_total_shares_short": _round(total_short, 2),
        "activity_volume": _round(volume, 2),
        "activity_short_volume_ratio": _round(ratio, 6),
        "activity_short_volume_ratio_prior_median": _round(prior_median, 6),
        "activity_short_volume_ratio_vs_median": _round(ratio_vs_median, 6),
        "candidate_signal_day_return": _round(signal_return, 6),
        "candidate_spy_signal_day_return": _round(spy_return, 6),
        "candidate_signal_return_vs_spy": _round(signal_vs_spy, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret5": _round(ret5, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_spy_ret20": _round(spy_ret20, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "uses_moomoo_daily_short_volume": True,
        "activity_only_not_positioning": True,
        "uses_free_ohlcv": True,
        "uses_llm": False,
        "trade_enabled": False,
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("date") or ""),
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("activity_short_volume_ratio_vs_median") or 0.0),
        -float(row.get("candidate_signal_return_vs_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
    )


def _activity_by_ticker(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        activity_date = _date10(row.get("activity_date"))
        if not ticker or not activity_date:
            continue
        out.setdefault(ticker, []).append({**row, "ticker": ticker, "activity_date": activity_date})
    for ticker in out:
        out[ticker].sort(key=lambda row: str(row.get("activity_date") or ""))
    return out


def _normalise_ohlcv_by_ticker(raw: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, payload in (raw or {}).items():
        rows = _normalise_rows(payload)
        if rows:
            out[str(ticker).upper()] = rows
    return out


def _normalise_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if hasattr(payload, "reset_index") and hasattr(payload, "to_dict"):
        frame = payload.reset_index()
        raw_rows = frame.to_dict("records")
    elif isinstance(payload, dict) and "ohlcv" in payload:
        raw_rows = payload.get("ohlcv") or []
    else:
        raw_rows = list(payload or [])
    rows = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        day = _date10(row.get("Date") or row.get("date") or row.get("index"))
        open_ = _float(row.get("Open") if "Open" in row else row.get("open"))
        high = _float(row.get("High") if "High" in row else row.get("high"))
        low = _float(row.get("Low") if "Low" in row else row.get("low"))
        close = _float(row.get("Close") if "Close" in row else row.get("close"))
        volume = _float(row.get("Volume") if "Volume" in row else row.get("volume"))
        if day is None or open_ is None or high is None or low is None or close is None:
            continue
        rows.append(
            {
                "Date": day,
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume or 0.0,
            }
        )
    rows.sort(key=lambda row: row["Date"])
    return rows


def _forward_paper_gate(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    closed = list(state.get("closed_positions") or [])
    pnls = [float(row.get("pnl") or 0.0) for row in closed]
    winners = [pnl for pnl in pnls if pnl > 0]
    by_ticker: dict[str, float] = {}
    for row in closed:
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + float(row.get("pnl") or 0.0)
    positive = {ticker: pnl for ticker, pnl in by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_share = max(positive.values()) / positive_total if positive_total > 0 else None
    hhi = sum((pnl / positive_total) ** 2 for pnl in positive.values()) if positive_total > 0 else None
    reasons: list[str] = []
    if len(closed) < int(config["forward_gate_min_closed_trades"]):
        reasons.append("forward_trade_count_below_min")
    if bool(config["forward_gate_positive_net_pnl"]) and sum(pnls) <= 0:
        reasons.append("forward_net_pnl_not_positive")
    if closed and len(winners) / len(closed) < float(config["forward_gate_min_win_rate"]):
        reasons.append("forward_win_rate_below_min")
    if max_share is None or max_share > float(config["forward_gate_max_single_ticker_positive_share"]):
        reasons.append("forward_single_ticker_concentration")
    if hhi is None or hhi > float(config["forward_gate_max_positive_hhi"]):
        reasons.append("forward_positive_hhi_concentration")
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "closed_trade_count": len(closed),
        "realized_pnl": _round(sum(pnls), 2),
        "win_rate": _round(len(winners) / len(closed), 4) if closed else None,
        "max_single_ticker_positive_share": _round(max_share, 6) if max_share is not None else None,
        "positive_pnl_hhi": _round(hhi, 6) if hhi is not None else None,
    }


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "backtester_adapter_changed": True,
        "run_adapter_changed": False,
        "replay_only": False,
        "trade_enabled": False,
        "daily_snapshot_exposed": False,
        "default_off_paper_only": True,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "uses_moomoo_daily_short_volume": True,
        "activity_only_not_positioning": True,
        "uses_llm": False,
    }


def _normalise_state(state: dict[str, Any]) -> None:
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_days"):
        if not isinstance(state.get(key), list):
            state[key] = []


def _config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    cfg["trade_enabled"] = False
    return cfg


def _date10(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)[:10]
    return text if len(text) == 10 else None


def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows) if _date(row)}


def _trading_dates(ohlcv_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    if "SPY" in ohlcv_by_ticker:
        return [_date(row) for row in ohlcv_by_ticker["SPY"] if _date(row)]
    dates = sorted({_date(row) for rows in ohlcv_by_ticker.values() for row in rows if _date(row)})
    return dates


def _next_trading_date(rows: list[dict[str, Any]], day: str) -> str | None:
    idx = _row_index(rows).get(day)
    if idx is None or idx + 1 >= len(rows):
        return None
    return _date(rows[idx + 1])


def _next_usable_trade_date(rows: list[dict[str, Any]], day: str) -> str | None:
    next_from_rows = _next_trading_date(rows, day)
    if next_from_rows:
        return next_from_rows
    try:
        current = date.fromisoformat(day)
    except ValueError:
        return None
    current += timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current.isoformat()


def _value(row: dict[str, Any], key: str) -> float | None:
    return _float(row.get(key) if key in row else row.get(key.lower()))


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = _value(rows[idx - 1], "Close")
    close = _value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = _value(rows[idx - lookback], "Close")
    close = _value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = _value(row, "Close")
        volume = _value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _close_location(row: dict[str, Any]) -> float | None:
    high = _value(row, "High")
    low = _value(row, "Low")
    close = _value(row, "Close")
    if high is None or low is None or close is None:
        return None
    span = high - low
    if span <= 0:
        return 0.5
    return (close - low) / span


def _realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    values = [_daily_return(rows, day_idx) for day_idx in range(idx - lookback + 1, idx + 1)]
    if any(value is None for value in values):
        return None
    valid = [float(value) for value in values if value is not None]
    mean_value = sum(valid) / len(valid)
    variance = sum((value - mean_value) ** 2 for value in valid) / len(valid)
    return math.sqrt(variance)


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float(value)
    if number is None:
        return None
    return round(number, digits)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value
