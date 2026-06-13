"""Default-off industry-stable core-flow paper sleeve.

Shared helper for the positive exp-20260608-007 replay lead. In already strong
and stable liquid industry groups, it admits the stable stock leader only when
the same signal date already has core A/B entry flow and excludes same-ticker
core overlap.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

try:
    import broad_market_sector_map
    import macro_relief_leadership_paper_sleeve as leader
    import market_state_router
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import broad_market_sector_map
    from quant import macro_relief_leadership_paper_sleeve as leader
    from quant import market_state_router
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage


SLEEVE_NAME = "INDUSTRY_STABLE_CORE_FLOW_PAPER"
RULE_VERSION = "industry_stable_core_flow_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "industry_stable_core_flow_confirmed_candidate_source_v1"
BASE_SOURCE_RULE_VERSION = "industry_stable_leadership_candidate_source_v1"
STATE_ROUTER_RULE_VERSION = "industry_stable_core_flow_state_tilt_mixed_balanced_normal_shared_v1"
STATE_ROUTER_CELL = market_state_router.MIXED_BALANCED_NORMAL_CELL
STATE_ROUTER_NOTIONAL_SCALAR = 1.5
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "industry_stable_core_flow" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "industry_stable_core_flow" / "snapshots.jsonl"
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
    "same_ticker_cooldown_days": 15,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "min_industry_liquid_count": 6,
    "min_group_median_ret20_excess_spy": 0.020,
    "min_group_ret20_positive_fraction": 0.62,
    "min_group_signal_positive_fraction": 0.50,
    "min_group_signal_relative_vs_spy_median": -0.002,
    "max_group_ret20_dispersion": 0.180,
    "max_group_median_realized_vol_20d": 0.055,
    "min_candidate_ret20_excess_spy": 0.025,
    "min_candidate_ret20_lead_vs_group": 0.005,
    "min_candidate_ret60_excess_spy": 0.000,
    "min_signal_return": 0.002,
    "min_signal_relative_vs_spy": 0.000,
    "min_close_location": 0.58,
    "min_volume_ratio_20d": 0.65,
    "max_volume_ratio_20d": 2.60,
    "min_ret5": -0.030,
    "max_ret5": 0.100,
    "max_realized_vol_20d": 0.070,
    "max_candidate_vol_vs_group_multiple": 1.20,
    "core_flow_confirmation_required": True,
    "same_ticker_core_overlap_excluded": True,
    "state_router_enabled": True,
    "state_router_cell": STATE_ROUTER_CELL,
    "state_router_notional_scalar": STATE_ROUTER_NOTIONAL_SCALAR,
    "state_router_rule_version": STATE_ROUTER_RULE_VERSION,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_industry_stable_core_flow_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_industry_stable_core_flow_snapshot(as_of: str, reason: str) -> dict[str, Any]:
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
        "state_router": _state_router_summary([], [], DEFAULT_CONFIG),
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "industry_stable_core_flow_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_industry_stable_core_flow_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_industry_stable_core_flow_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_industry_stable_core_flow_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_industry_stable_core_flow_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_industry_stable_core_flow_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def build_industry_stable_core_flow_snapshot(
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
    as_of_date = _date10(as_of)
    working_state = deepcopy(
        state if state is not None else load_industry_stable_core_flow_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_industry_stable_core_flow_snapshot(as_of_date, "missing_ohlcv")
    if "SPY" not in rows_by_ticker:
        return empty_industry_stable_core_flow_snapshot(as_of_date, "missing_spy_ohlcv")

    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    if not sector_map:
        return empty_industry_stable_core_flow_snapshot(as_of_date, "missing_sector_entries")

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
    candidates, contexts, scan = build_industry_stable_core_flow_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        sector_entries=sector_map,
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
    )
    selected, rejected = select_industry_stable_core_flow_paper_trades(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        existing_state=working_state,
        config=cfg,
    )
    selected = _apply_state_router_to_trades(
        selected,
        rows_by_ticker=rows_by_ticker,
        config=cfg,
    )
    new_pending_entries: list[dict[str, Any]] = []
    if cfg.get("paper_enabled", True):
        for trade in selected:
            pending = _pending_entry_from_trade(trade, cfg)
            if not leader._has_pending_open_or_closed_decision(
                working_state,
                pending["decision_id"],
            ):
                working_state["pending_entries"].append(pending)
                new_pending_entries.append(pending)
    if not selected and not contexts:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_stable_industry_context"))
    elif not selected and contexts and not candidates:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_core_flow_confirmed_candidate"))

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        candidates=candidates,
        selected=selected,
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
        save_industry_stable_core_flow_state(working_state, state_path)
        append_industry_stable_core_flow_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_industry_stable_core_flow_historical_trades(
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
        "industry_contexts_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in _trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, contexts, scan = build_industry_stable_core_flow_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_map,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
            require_exit_data=True,
        )
        selected, rejected = select_industry_stable_core_flow_paper_trades(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            config=cfg,
        )
        selected = _apply_state_router_to_trades(
            selected,
            rows_by_ticker=rows_by_ticker,
            config=cfg,
        )
        window_trades = [{**row, "window": label} for row in selected]
        all_trades.extend(window_trades)
        audit["selected_by_window"][label] = len(window_trades)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
        audit["industry_contexts_by_window"][label] = contexts[:100]
    return all_trades, _safe(audit)


def build_industry_stable_core_flow_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    config: dict[str, Any] | None = None,
    require_exit_data: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: leader._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    date_set = {_date10(day) for day in dates}
    core_entries_by_date = core_entries_by_date or {}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(date_set),
        "days_with_stable_industry_groups": 0,
        "stable_industry_group_rows": 0,
        "days_with_raw_candidates": 0,
        "raw_candidates_before_core_flow_filter": 0,
        "raw_candidates_after_core_flow_filter": 0,
        "raw_candidates_missing_core_flow": 0,
        "raw_candidates_excluded_same_ticker_core_overlap": 0,
        "core_flow_confirmed_dates": 0,
        "unique_candidate_tickers": 0,
        "rule_version": SOURCE_RULE_VERSION,
        "base_rule_version": BASE_SOURCE_RULE_VERSION,
        "core_flow_confirmation_required": True,
        "same_ticker_core_overlap_excluded": True,
    }
    candidate_tickers: set[str] = set()

    for signal_date in sorted(date_set):
        group_contexts, stats_by_ticker = _industry_contexts_for_day(
            rows_by_ticker=rows_by_ticker,
            indices=indices,
            sector_entries=sector_entries,
            signal_date=signal_date,
            config=cfg,
            require_exit_data=require_exit_data,
        )
        if not group_contexts:
            continue
        scan["days_with_stable_industry_groups"] += 1
        scan["stable_industry_group_rows"] += len(group_contexts)

        raw_rows: list[dict[str, Any]] = []
        filtered_rows: list[dict[str, Any]] = []
        for ticker, stats in stats_by_ticker.items():
            context = group_contexts.get(str(stats.get("group_key") or ""))
            if context is None:
                continue
            row = _candidate_from_stats(
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
                stats=stats,
                config=cfg,
            )
            if row is None:
                continue
            core_entries = core_entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(core_entries)
            row["same_day_ab_overlap"] = bool(core_entries)
            row["same_ticker_ab_overlap"] = any(
                str(trade.get("ticker") or "").upper() == row["ticker"]
                for trade in core_entries
            )
            row["core_flow_confirmation"] = {
                "required": True,
                "same_day_ab_entry_count": row["same_day_ab_entry_count"],
                "same_day_ab_overlap": row["same_day_ab_overlap"],
                "same_ticker_core_overlap": row["same_ticker_ab_overlap"],
                "same_ticker_core_overlap_excluded": True,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
                "rule_version": SOURCE_RULE_VERSION,
            }
            raw_rows.append(row)
            if not row["same_day_ab_overlap"]:
                scan["raw_candidates_missing_core_flow"] += 1
                continue
            if row["same_ticker_ab_overlap"]:
                scan["raw_candidates_excluded_same_ticker_core_overlap"] += 1
                continue
            filtered_rows.append(row)
            candidate_tickers.add(row["ticker"])

        scan["raw_candidates_before_core_flow_filter"] += len(raw_rows)
        if not filtered_rows:
            top = sorted(raw_rows, key=_candidate_sort_key)[0] if raw_rows else None
            contexts.append(
                {
                    "date": signal_date,
                    "stable_industry_group_count": len(group_contexts),
                    "raw_candidate_count_before_core_flow_filter": len(raw_rows),
                    "raw_candidate_count_after_core_flow_filter": 0,
                    "core_flow_confirmation_required": True,
                    "same_ticker_core_overlap_excluded": True,
                    "rule_version": SOURCE_RULE_VERSION,
                    **(
                        {
                            "top_candidate_before_core_flow": top["ticker"],
                            "top_group_key_before_core_flow": top["candidate_group_key"],
                            "top_score_before_core_flow": top["candidate_score"],
                        }
                        if top
                        else {}
                    ),
                }
            )
            continue
        filtered_rows.sort(key=_candidate_sort_key)
        candidates.extend(filtered_rows)
        scan["days_with_raw_candidates"] += 1
        scan["raw_candidates_after_core_flow_filter"] += len(filtered_rows)
        scan["core_flow_confirmed_dates"] += 1
        top = filtered_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "stable_industry_group_count": len(group_contexts),
                "raw_candidate_count_before_core_flow_filter": len(raw_rows),
                "raw_candidate_count_after_core_flow_filter": len(filtered_rows),
                "top_candidate": top["ticker"],
                "top_group_key": top["candidate_group_key"],
                "top_score": top["candidate_score"],
                "top_ret20_lead_vs_group": top["candidate_ret20_lead_vs_group"],
                "top_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_realized_vol_20d": top["candidate_realized_vol_20d"],
                "core_flow_confirmation_required": True,
                "same_ticker_core_overlap_excluded": True,
                "rule_version": SOURCE_RULE_VERSION,
            }
        )

    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    scan.update({"unique_candidate_tickers": len(candidate_tickers), **_parameter_summary(cfg)})
    return candidates, contexts, scan


def select_industry_stable_core_flow_paper_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _config(config)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    all_dates = _trading_dates(rows_by_ticker)
    date_pos = {day: idx for idx, day in enumerate(all_dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    if existing_state:
        for row in (existing_state.get("pending_entries") or []) + (
            existing_state.get("open_positions") or []
        ):
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            date_value = str(row.get("signal_date") or row.get("date") or "")[:10]
            pos = date_pos.get(date_value)
            if ticker and pos is not None:
                next_allowed_pos_by_ticker[ticker] = max(
                    next_allowed_pos_by_ticker.get(ticker, -1),
                    pos + int(cfg["same_ticker_cooldown_days"]),
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
        trade = replay_trade_from_candidate(
            rows_by_ticker=rows_by_ticker,
            candidate=row,
            config=cfg,
        )
        if trade is None:
            rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    return selected, rejected


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
        "decision_id": f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}",
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


def _industry_contexts_for_day(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
    config: dict[str, Any],
    require_exit_data: bool,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats_by_ticker: dict[str, dict[str, Any]] = {}
    for ticker, meta in sector_entries.items():
        stats = _candidate_stats(
            rows_by_ticker=rows_by_ticker,
            indices=indices,
            ticker=ticker,
            signal_date=signal_date,
            config=config,
            require_exit_data=require_exit_data,
        )
        if stats is None:
            continue
        group = _group_key(meta)
        stats["group_key"] = group
        stats_by_ticker[ticker] = stats
        groups[group].append(stats)

    contexts: dict[str, dict[str, Any]] = {}
    for group, rows in groups.items():
        if len(rows) < int(config["min_industry_liquid_count"]):
            continue
        ret20_values = [float(row["ret20_excess_spy"]) for row in rows]
        signal_values = [float(row["signal_relative_vs_spy"]) for row in rows]
        vol_values = [float(row["realized_vol_20d"]) for row in rows]
        dispersion = _p90_minus_p10(ret20_values)
        if dispersion is None:
            continue
        median_ret20 = median(ret20_values)
        median_signal = median(signal_values)
        median_vol = median(vol_values)
        positive_fraction = sum(1 for value in ret20_values if value > 0.0) / len(rows)
        signal_positive_fraction = sum(1 for value in signal_values if value > 0.0) / len(rows)
        context = {
            "date": signal_date,
            "group_key": group,
            "liquid_group_count": len(rows),
            "median_ret20_excess_spy": leader._round(median_ret20, 6),
            "ret20_positive_fraction": leader._round(positive_fraction, 6),
            "median_signal_relative_vs_spy": leader._round(median_signal, 6),
            "signal_positive_fraction": leader._round(signal_positive_fraction, 6),
            "ret20_dispersion_p90_minus_p10": leader._round(dispersion, 6),
            "median_realized_vol_20d": leader._round(median_vol, 6),
            "rule_version": BASE_SOURCE_RULE_VERSION,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
        }
        if median_ret20 < float(config["min_group_median_ret20_excess_spy"]):
            continue
        if positive_fraction < float(config["min_group_ret20_positive_fraction"]):
            continue
        if signal_positive_fraction < float(config["min_group_signal_positive_fraction"]):
            continue
        if median_signal < float(config["min_group_signal_relative_vs_spy_median"]):
            continue
        if dispersion > float(config["max_group_ret20_dispersion"]):
            continue
        if median_vol > float(config["max_group_median_realized_vol_20d"]):
            continue
        contexts[group] = {**context, "passed": True}
    return contexts, stats_by_ticker


def _candidate_stats(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    config: dict[str, Any],
    require_exit_data: bool,
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if require_exit_data and idx + int(config["hold_days"]) >= len(rows):
        return None
    close = leader._positive_float(rows[idx].get("close"))
    if close is None or close < float(config["min_price"]):
        return None
    adv20 = leader._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None
    signal_return = leader._daily_return(rows, idx)
    spy_signal_return = leader._daily_return(spy_rows, spy_idx)
    ret5 = leader._ret(rows, idx, 5)
    ret20 = leader._ret(rows, idx, 20)
    ret60 = leader._ret(rows, idx, 60)
    spy_ret20 = leader._ret(spy_rows, spy_idx, 20)
    spy_ret60 = leader._ret(spy_rows, spy_idx, 60)
    close_location = leader._close_location(rows[idx])
    volume_ratio = leader._volume_ratio(rows, idx)
    realized_vol20 = leader._realized_vol(rows, idx, 20)
    required = [
        signal_return,
        spy_signal_return,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        close_location,
        volume_ratio,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    return {
        "ticker": ticker,
        "signal_return": signal_return,
        "spy_signal_return": spy_signal_return,
        "signal_relative_vs_spy": float(signal_return) - float(spy_signal_return),
        "ret5": ret5,
        "ret20": ret20,
        "ret60": ret60,
        "ret20_excess_spy": float(ret20) - float(spy_ret20),
        "ret60_excess_spy": float(ret60) - float(spy_ret60),
        "close_location": close_location,
        "volume_ratio_20d": volume_ratio,
        "avg_dollar_volume_20d": adv20,
        "realized_vol_20d": realized_vol20,
    }


def _candidate_from_stats(
    *,
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
    stats: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    group_median = float(context["median_ret20_excess_spy"])
    group_median_vol = float(context["median_realized_vol_20d"])
    if float(stats["ret20_excess_spy"]) < float(config["min_candidate_ret20_excess_spy"]):
        return None
    ret20_lead_vs_group = float(stats["ret20_excess_spy"]) - group_median
    if ret20_lead_vs_group < float(config["min_candidate_ret20_lead_vs_group"]):
        return None
    if float(stats["ret60_excess_spy"]) < float(config["min_candidate_ret60_excess_spy"]):
        return None
    if float(stats["signal_return"]) < float(config["min_signal_return"]):
        return None
    if float(stats["signal_relative_vs_spy"]) < float(config["min_signal_relative_vs_spy"]):
        return None
    if float(stats["close_location"]) < float(config["min_close_location"]):
        return None
    if not (
        float(config["min_volume_ratio_20d"])
        <= float(stats["volume_ratio_20d"])
        <= float(config["max_volume_ratio_20d"])
    ):
        return None
    if not (
        float(config["min_ret5"])
        <= float(stats["ret5"])
        <= float(config["max_ret5"])
    ):
        return None
    max_vol = min(
        float(config["max_realized_vol_20d"]),
        max(0.015, group_median_vol * float(config["max_candidate_vol_vs_group_multiple"])),
    )
    if float(stats["realized_vol_20d"]) > max_vol:
        return None
    meta = sector_entries[ticker]
    liquidity_score = math.log10(max(float(stats["avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
    score = (
        1.55 * ret20_lead_vs_group
        + 1.20 * float(stats["ret20_excess_spy"])
        + 0.65 * float(stats["ret60_excess_spy"])
        + 0.60 * float(stats["signal_relative_vs_spy"])
        + 0.24 * float(stats["close_location"])
        + 0.05 * min(float(stats["volume_ratio_20d"]), 2.6)
        + 0.04 * liquidity_score
        - 0.90 * float(stats["realized_vol_20d"])
        - 0.20 * max(float(stats["ret5"]), 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": SLEEVE_NAME,
        "candidate_score": leader._round(score, 6),
        "candidate_group_key": context["group_key"],
        "candidate_ret20_lead_vs_group": leader._round(ret20_lead_vs_group, 6),
        "candidate_signal_day_return": leader._round(stats["signal_return"], 6),
        "candidate_signal_relative_vs_spy": leader._round(
            stats["signal_relative_vs_spy"],
            6,
        ),
        "candidate_close_location": leader._round(stats["close_location"], 6),
        "candidate_volume_ratio_20d": leader._round(stats["volume_ratio_20d"], 6),
        "candidate_avg_dollar_volume_20d": leader._round(stats["avg_dollar_volume_20d"], 2),
        "candidate_ret5": leader._round(stats["ret5"], 6),
        "candidate_ret20_excess_spy": leader._round(stats["ret20_excess_spy"], 6),
        "candidate_ret60_excess_spy": leader._round(stats["ret60_excess_spy"], 6),
        "candidate_realized_vol_20d": leader._round(stats["realized_vol_20d"], 6),
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "sector_coverage_status": meta.get("sector_coverage_status") or meta.get("status"),
        "industry_stable_leadership_context": context,
        "rule_version": SOURCE_RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _apply_state_router_to_trades(
    trades: list[dict[str, Any]],
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _apply_state_router_to_trade(trade, rows_by_ticker=rows_by_ticker, config=config)
        for trade in trades
    ]


def _apply_state_router_to_trade(
    trade: dict[str, Any],
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    row = deepcopy(trade)
    enabled = bool(config.get("state_router_enabled", True))
    cell = str(config.get("state_router_cell") or STATE_ROUTER_CELL)
    scalar = float(config.get("state_router_notional_scalar") or STATE_ROUTER_NOTIONAL_SCALAR)
    entry_date = str(row.get("entry_date") or "")[:10]
    state = (
        market_state_router.state_for_entry_date(
            ohlcv_by_ticker=rows_by_ticker,
            entry_date=entry_date,
        )
        if entry_date
        else None
    )
    combined_state = state.get("combined_state") if state else None
    cell_match = combined_state == cell
    applies = bool(enabled and cell_match)
    status = "disabled"
    if enabled and state is None:
        status = "state_unavailable"
    elif enabled and cell_match:
        status = "cell_match_scaled"
    elif enabled:
        status = "cell_miss"

    base_notional = leader._float_or_none(row.get("paper_notional_usd"))
    base_pnl = leader._float_or_none(row.get("pnl"))
    row.update(
        {
            "entry_market_state": state,
            "combined_state": combined_state,
            "state_router_cell": cell,
            "state_router_cell_match": cell_match,
            "state_router_applied": applies,
            "state_router_enabled": enabled,
            "state_router_status": status,
            "state_router_rule_version": str(
                config.get("state_router_rule_version") or STATE_ROUTER_RULE_VERSION
            ),
            "state_router_scalar": scalar if applies else 1.0,
            "state_router_base_paper_notional_usd": leader._round(base_notional, 2),
            "state_router_base_pnl": leader._round(base_pnl, 2),
            "state_router_incremental_pnl": 0.0,
        }
    )
    if applies and base_notional is not None:
        row["paper_notional_usd"] = leader._round(base_notional * scalar, 2)
        row["notional_usd"] = leader._round(base_notional * scalar, 2)
    if applies and base_pnl is not None:
        row["state_router_incremental_pnl"] = leader._round(base_pnl * (scalar - 1.0), 2)
        row["pnl"] = leader._round(base_pnl * scalar, 2)
    return row


def _pending_entry_from_trade(trade: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(trade)
    for key in (
        "entry_date",
        "entry_raw_open",
        "entry_price",
        "exit_date",
        "exit_raw_close",
        "exit_price",
        "pnl",
        "pnl_pct_net",
    ):
        out.pop(key, None)
    notional = leader._positive_float(trade.get("paper_notional_usd"))
    if notional is None:
        notional = float(config["paper_notional_usd"])
    out.update(
        {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "paper_notional_usd": leader._round(notional, 2),
            "notional_usd": leader._round(notional, 2),
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
    selected: list[dict[str, Any]],
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
        "candidate_count": len(selected),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "candidate": selected[0] if selected else None,
        "candidates": selected,
        "rejected_candidates": rejected[:50],
        "industry_stable_core_flow_context": {
            **scan,
            "read_only": True,
            "trade_enabled": False,
            "context_samples": contexts[:10],
        },
        "context_scan": scan,
        "candidate_universe": _candidate_universe_summary(candidate_universe, rows_by_ticker),
        "new_pending_entries": new_pending_entries,
        "new_pending_count": len(new_pending_entries),
        "state_router": _state_router_summary(selected, new_pending_entries, config),
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


def _state_router_summary(
    selected: list[dict[str, Any]],
    new_pending_entries: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    rows = selected or new_pending_entries or []
    statuses = Counter(str(row.get("state_router_status") or "unknown") for row in rows)
    states = Counter(str(row.get("combined_state") or "unknown") for row in rows)
    applied = [row for row in rows if row.get("state_router_applied")]
    return {
        "enabled": bool(config.get("state_router_enabled", True)),
        "rule_version": str(config.get("state_router_rule_version") or STATE_ROUTER_RULE_VERSION),
        "cell": str(config.get("state_router_cell") or STATE_ROUTER_CELL),
        "notional_scalar": float(
            config.get("state_router_notional_scalar") or STATE_ROUTER_NOTIONAL_SCALAR
        ),
        "known_at": market_state_router.STATE_KNOWN_AT,
        "uses_free_ohlcv_only": True,
        "requires_tickers": ["SPY", "QQQ"],
        "selected_count": len(selected),
        "new_pending_count": len(new_pending_entries),
        "applied_count": len(applied),
        "status_counts": dict(sorted(statuses.items())),
        "combined_state_counts": dict(sorted(states.items())),
    }


def _resolve_sector_entries(
    *,
    sector_entries: dict[str, dict[str, Any]] | None,
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    allowed = (
        {str(ticker).upper() for ticker in candidate_universe}
        if isinstance(candidate_universe, list)
        else set(rows_by_ticker)
    )
    if isinstance(candidate_universe, dict) and candidate_universe.get("tickers"):
        allowed = {str(ticker).upper() for ticker in candidate_universe.get("tickers") or []}

    sources: list[dict[str, Any]] = []
    if sector_entries:
        sources.append(sector_entries)
    if isinstance(candidate_universe, dict):
        for key in ("records", "entries"):
            if isinstance(candidate_universe.get(key), dict):
                sources.append(candidate_universe[key])
    for raw_entries in sources:
        out = _filter_sector_entries(raw_entries, allowed=allowed, rows_by_ticker=rows_by_ticker)
        if out:
            return out

    # Governance fallback feeds carry ticker/title/theme metadata without any
    # sector fields, so an empty resolution falls through to the persisted
    # broad-market sector cache restricted to the same allowed tickers.
    cache = broad_market_sector_map.load_cache()
    cache_entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
    return _filter_sector_entries(cache_entries, allowed=allowed, rows_by_ticker=rows_by_ticker)


def _filter_sector_entries(
    raw_entries: dict[str, Any],
    *,
    allowed: set[str],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
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
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_days", [])


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


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("candidate_ret20_lead_vs_group") or 0.0),
        -float(row.get("candidate_ret20_excess_spy") or 0.0),
        float(row.get("candidate_realized_vol_20d") or 999.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("candidate_group_key") or ""),
        str(row.get("ticker") or ""),
    )


def _group_key(meta: dict[str, Any]) -> str:
    industry = str(meta.get("industry") or "").strip()
    if industry and industry.lower() != "unknown":
        return industry
    return str(meta.get("sector") or "unknown").strip() or "unknown"


def _p90_minus_p10(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    ordered = sorted(values)
    p10 = ordered[max(0, int((len(ordered) - 1) * 0.10))]
    p90 = ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.90))]
    return p90 - p10


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
        "min_industry_liquid_count",
        "min_group_median_ret20_excess_spy",
        "min_group_ret20_positive_fraction",
        "min_group_signal_positive_fraction",
        "min_group_signal_relative_vs_spy_median",
        "max_group_ret20_dispersion",
        "max_group_median_realized_vol_20d",
        "min_candidate_ret20_excess_spy",
        "min_candidate_ret20_lead_vs_group",
        "min_candidate_ret60_excess_spy",
        "min_signal_return",
        "min_signal_relative_vs_spy",
        "min_close_location",
        "min_volume_ratio_20d",
        "max_volume_ratio_20d",
        "min_ret5",
        "max_ret5",
        "max_realized_vol_20d",
        "max_candidate_vol_vs_group_multiple",
        "core_flow_confirmation_required",
        "same_ticker_core_overlap_excluded",
        "state_router_enabled",
        "state_router_cell",
        "state_router_notional_scalar",
        "state_router_rule_version",
    ]
    return {key: config[key] for key in keys}


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    cfg["core_flow_confirmation_required"] = True
    cfg["same_ticker_core_overlap_excluded"] = True
    return cfg


def _date10(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


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
        "state_router_rule_version": STATE_ROUTER_RULE_VERSION,
        "state_router_cell": STATE_ROUTER_CELL,
        "state_router_notional_scalar": STATE_ROUTER_NOTIONAL_SCALAR,
        "state_router_known_at": market_state_router.STATE_KNOWN_AT,
        "state_router_requires_tickers": ["SPY", "QQQ"],
        "adapter_status": "shared_default_off_paper_helper",
        "scope": "default_off_industry_stable_core_flow_paper_attribution",
    }
