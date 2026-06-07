"""Default-off industry-relative laggard repair paper sleeve.

Shared helper for the positive exp-20260607-007 replay lead. The helper emits
observe-only paper candidates and historical paper trades for a fixed free-OHLCV
industry-relative repair source. It never alters live orders, core ranking,
sizing, exits, watchlists, LLM, or news behavior.
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
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import broad_market_sector_map
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage


SLEEVE_NAME = "INDUSTRY_RELATIVE_LAGGARD_REPAIR_PAPER"
RULE_VERSION = "industry_relative_laggard_repair_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "industry_relative_laggard_repair_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "industry_relative_laggard_repair" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "industry_relative_laggard_repair"
    / "snapshots.jsonl"
)

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
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
    "hold_days": 10,
    "same_ticker_cooldown_days": 15,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "group_lookback_days": 20,
    "recent_lookback_days": 5,
    "trend_lookback_days": 60,
    "min_industry_liquid_count": 5,
    "min_group_median_ret20_excess_spy": 0.018,
    "min_group_ret20_positive_fraction": 0.55,
    "min_group_median_ret5_excess_spy": -0.015,
    "min_industry_lag_20d": 0.055,
    "max_industry_lag_20d": 0.220,
    "min_candidate_ret20_excess_spy": -0.095,
    "min_candidate_ret60_excess_spy": -0.060,
    "min_candidate_ret5_excess_spy": -0.010,
    "min_signal_return": 0.004,
    "max_signal_return": 0.080,
    "min_signal_relative_vs_spy": 0.006,
    "min_close_location": 0.62,
    "min_volume_ratio_20d": 0.75,
    "max_volume_ratio_20d": 2.60,
    "max_realized_vol_20d": 0.080,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_industry_relative_laggard_repair_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_industry_relative_laggard_repair_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_industry_relative_laggard_repair_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_industry_relative_laggard_repair_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_industry_relative_laggard_repair_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_industry_relative_laggard_repair_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_industry_relative_laggard_repair_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
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
        "closed_count_today": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "industry_repair_context": {
            "status": reason,
            "rule_version": SOURCE_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "candidate_count": 0,
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_industry_relative_laggard_repair_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    core_entries: list[dict[str, Any]] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker or {})
    if not rows_by_ticker:
        return empty_industry_relative_laggard_repair_paper_sleeve_snapshot(
            as_of_date,
            "missing_ohlcv",
        )
    if "SPY" not in rows_by_ticker:
        return empty_industry_relative_laggard_repair_paper_sleeve_snapshot(
            as_of_date,
            "missing_spy_ohlcv",
        )

    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    if not sector_map:
        return empty_industry_relative_laggard_repair_paper_sleeve_snapshot(
            as_of_date,
            "missing_sector_entries",
        )

    working_state = deepcopy(
        state
        if state is not None
        else load_industry_relative_laggard_repair_paper_state(state_path)
    )
    _normalise_state(working_state)
    lifecycle = _advance_paper_state(
        rows_by_ticker=rows_by_ticker,
        state=working_state,
        as_of_date=as_of_date,
        config=cfg,
    )

    candidates, contexts, scan = build_industry_relative_laggard_repair_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        sector_entries=sector_map,
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
    )
    selected, rejected = _select_candidates_for_paper(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        state=working_state,
        config=cfg,
        create_trades=False,
    )
    pending = [_pending_entry_from_candidate(row, cfg) for row in selected]
    if cfg.get("paper_enabled", True):
        existing_ids = _decision_ids(working_state)
        for row in pending:
            if row["decision_id"] not in existing_ids:
                working_state["pending_entries"].append(row)
                existing_ids.add(row["decision_id"])

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
        "trade_enabled_reason": "default_off_until_forward_gate_and_trade_adapter_pass",
        "candidate_count": len(selected),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(pending),
        "pending_count": len(working_state["pending_entries"]),
        "open_position_count": len(working_state["open_positions"]),
        "closed_position_count": len(working_state["closed_positions"]),
        "closed_count_today": len(lifecycle["closed_this_run"]),
        "realized_pnl_to_date": _round(
            sum(float(row.get("pnl") or 0.0) for row in working_state["closed_positions"]),
            2,
        ),
        "unrealized_pnl": _unrealized_pnl(
            rows_by_ticker=rows_by_ticker,
            open_positions=working_state["open_positions"],
            as_of_date=as_of_date,
        ),
        "candidates": selected,
        "rejected_candidates": rejected[:50],
        "new_pending_entries": pending,
        "opened_positions_this_run": lifecycle["opened_this_run"],
        "closed_positions_this_run": lifecycle["closed_this_run"],
        "skipped_entries_this_run": lifecycle["skipped_this_run"],
        "industry_repair_context": {
            **scan,
            "rule_version": SOURCE_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "candidate_count": len(selected),
            "raw_candidate_count": len(candidates),
            "context_samples": contexts[:10],
        },
        "candidate_universe": _candidate_universe_summary(candidate_universe, rows_by_ticker),
        "forward_paper_gate": _forward_paper_gate(working_state, cfg),
        "parameters": _parameter_summary(cfg),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }
    if persist:
        save_industry_relative_laggard_repair_paper_state(working_state, state_path)
        append_industry_relative_laggard_repair_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_industry_relative_laggard_repair_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
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
        candidates, contexts, scan = build_industry_relative_laggard_repair_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_map,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
            require_exit_data=True,
        )
        selected, rejected = _select_candidates_for_paper(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            state=empty_industry_relative_laggard_repair_paper_state(),
            config=cfg,
            create_trades=True,
        )
        window_trades = [{**row, "window": label} for row in selected]
        all_trades.extend(window_trades)
        audit["selected_by_window"][label] = len(window_trades)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
        audit["industry_contexts_by_window"][label] = contexts[:100]
    return all_trades, _safe(audit)


def build_industry_relative_laggard_repair_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    config: dict[str, Any] | None = None,
    require_exit_data: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: _row_index(rows) for ticker, rows in rows_by_ticker.items()}
    date_set = set(_date10(day) for day in dates)
    core_entries_by_date = core_entries_by_date or {}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(date_set),
        "days_with_strong_groups": 0,
        "days_with_raw_candidates": 0,
        "strong_group_rows": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": SOURCE_RULE_VERSION,
    }
    candidate_tickers: set[str] = set()

    for signal_date in sorted(date_set):
        group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ticker in sorted(sector_entries):
            metrics = _ticker_day_metrics(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                config=cfg,
                require_exit_data=require_exit_data,
            )
            if metrics is not None:
                group_members[metrics["group_key"]].append(metrics)

        group_summaries = _strong_group_summaries(group_members, cfg)
        if not group_summaries:
            continue
        scan["days_with_strong_groups"] += 1
        scan["strong_group_rows"] += len(group_summaries)

        day_rows: list[dict[str, Any]] = []
        for group_key, rows in group_members.items():
            group = group_summaries.get(group_key)
            if group is None:
                continue
            for metrics in rows:
                row = _candidate_from_metrics(metrics=metrics, group=group, config=cfg)
                if row is None:
                    continue
                core_entries = core_entries_by_date.get(signal_date, [])
                row["same_day_ab_entry_count"] = len(core_entries)
                row["same_day_ab_overlap"] = bool(core_entries)
                row["same_ticker_ab_overlap"] = any(
                    str(trade.get("ticker") or "").upper() == row["ticker"]
                    for trade in core_entries
                )
                day_rows.append(row)
                candidate_tickers.add(str(row["ticker"]))

        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_candidates"] += 1
        scan["raw_candidate_rows"] += len(day_rows)
        top = day_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "strong_group_count": len(group_summaries),
                "top_candidate": top["ticker"],
                "top_group_key": top["candidate_group_key"],
                "top_score": top["candidate_score"],
                "top_industry_lag_20d": top["candidate_industry_lag_20d"],
                "top_signal_relative_vs_spy": top["candidate_signal_relative_vs_spy"],
                "top_repair_vs_group_5d": top["candidate_repair_vs_group_5d"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            *_candidate_sort_key(row),
        )
    )
    scan.update({"unique_candidate_tickers": len(candidate_tickers), **_parameter_summary(cfg)})
    return candidates, contexts, scan


def _ticker_day_metrics(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    config: dict[str, Any],
    require_exit_data: bool = False,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    min_idx = max(
        int(config["trend_lookback_days"]),
        int(config["group_lookback_days"]),
        int(config["recent_lookback_days"]),
        20,
    )
    if idx is None or spy_idx is None or idx < min_idx or spy_idx < min_idx:
        return None
    if require_exit_data and idx + int(config["hold_days"]) >= len(rows):
        return None
    close = _value(rows[idx], "close")
    if close is None or close < float(config["min_price"]):
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None

    group_days = int(config["group_lookback_days"])
    recent_days = int(config["recent_lookback_days"])
    trend_days = int(config["trend_lookback_days"])
    ret20 = _ret(rows, idx, group_days)
    spy_ret20 = _ret(spy_rows, spy_idx, group_days)
    ret5 = _ret(rows, idx, recent_days)
    spy_ret5 = _ret(spy_rows, spy_idx, recent_days)
    ret60 = _ret(rows, idx, trend_days)
    spy_ret60 = _ret(spy_rows, spy_idx, trend_days)
    signal_return = _daily_return(rows, idx)
    spy_signal_return = _daily_return(spy_rows, spy_idx)
    close_location = _close_location(rows[idx])
    volume_ratio = _volume_ratio(rows, idx)
    realized_vol20 = _realized_vol(rows, idx)
    required = [
        ret20,
        spy_ret20,
        ret5,
        spy_ret5,
        ret60,
        spy_ret60,
        signal_return,
        spy_signal_return,
        close_location,
        volume_ratio,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None

    meta = sector_entries[ticker]
    key = _group_key(meta)
    if key is None:
        return None
    return {
        "date": signal_date,
        "ticker": ticker,
        "group_key": key,
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "sector_coverage_status": meta.get("sector_coverage_status") or meta.get("status"),
        "close": close,
        "adv20": adv20,
        "ret20_excess_spy": float(ret20) - float(spy_ret20),
        "ret5_excess_spy": float(ret5) - float(spy_ret5),
        "ret60_excess_spy": float(ret60) - float(spy_ret60),
        "signal_return": float(signal_return),
        "signal_relative_vs_spy": float(signal_return) - float(spy_signal_return),
        "close_location": float(close_location),
        "volume_ratio_20d": float(volume_ratio),
        "realized_vol_20d": float(realized_vol20),
    }


def _strong_group_summaries(
    group_members: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for group_key, rows in group_members.items():
        if len(rows) < int(config["min_industry_liquid_count"]):
            continue
        ret20_values = [float(row["ret20_excess_spy"]) for row in rows]
        ret5_values = [float(row["ret5_excess_spy"]) for row in rows]
        positive_fraction = sum(value > 0.0 for value in ret20_values) / len(ret20_values)
        group_median_ret20 = median(ret20_values)
        group_median_ret5 = median(ret5_values)
        if group_median_ret20 < float(config["min_group_median_ret20_excess_spy"]):
            continue
        if positive_fraction < float(config["min_group_ret20_positive_fraction"]):
            continue
        if group_median_ret5 < float(config["min_group_median_ret5_excess_spy"]):
            continue
        out[group_key] = {
            "liquid_group_count": len(rows),
            "median_ret20_excess_spy": group_median_ret20,
            "median_ret5_excess_spy": group_median_ret5,
            "ret20_positive_fraction": positive_fraction,
        }
    return out


def _candidate_from_metrics(
    *,
    metrics: dict[str, Any],
    group: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    group_lag_20d = group["median_ret20_excess_spy"] - metrics["ret20_excess_spy"]
    if group_lag_20d < float(config["min_industry_lag_20d"]):
        return None
    if group_lag_20d > float(config["max_industry_lag_20d"]):
        return None
    if metrics["ret20_excess_spy"] < float(config["min_candidate_ret20_excess_spy"]):
        return None
    if metrics["ret60_excess_spy"] < float(config["min_candidate_ret60_excess_spy"]):
        return None
    if metrics["ret5_excess_spy"] < float(config["min_candidate_ret5_excess_spy"]):
        return None
    if metrics["signal_return"] < float(config["min_signal_return"]):
        return None
    if metrics["signal_return"] > float(config["max_signal_return"]):
        return None
    if metrics["signal_relative_vs_spy"] < float(config["min_signal_relative_vs_spy"]):
        return None
    if metrics["close_location"] < float(config["min_close_location"]):
        return None
    if metrics["volume_ratio_20d"] < float(config["min_volume_ratio_20d"]):
        return None
    if metrics["volume_ratio_20d"] > float(config["max_volume_ratio_20d"]):
        return None
    if metrics["realized_vol_20d"] > float(config["max_realized_vol_20d"]):
        return None

    repair_vs_group_5d = metrics["ret5_excess_spy"] - group["median_ret5_excess_spy"]
    score = (
        1.60 * group_lag_20d
        + 1.45 * metrics["signal_relative_vs_spy"]
        + 0.90 * repair_vs_group_5d
        + 0.85 * group["median_ret20_excess_spy"]
        + 0.45 * metrics["close_location"]
        + 0.18 * metrics["ret60_excess_spy"]
        + 0.04 * math.log10(max(metrics["adv20"], 1.0) / 1_000_000.0)
        - 0.65 * metrics["realized_vol_20d"]
        - 0.05 * abs(metrics["volume_ratio_20d"] - 1.2)
    )
    return {
        "date": metrics["date"],
        "ticker": metrics["ticker"],
        "source": SLEEVE_NAME,
        "candidate_score": _round(score, 6),
        "candidate_group_key": metrics["group_key"],
        "candidate_industry_lag_20d": _round(group_lag_20d, 6),
        "candidate_repair_vs_group_5d": _round(repair_vs_group_5d, 6),
        "candidate_ret20_excess_spy": _round(metrics["ret20_excess_spy"], 6),
        "candidate_ret5_excess_spy": _round(metrics["ret5_excess_spy"], 6),
        "candidate_ret60_excess_spy": _round(metrics["ret60_excess_spy"], 6),
        "candidate_signal_day_return": _round(metrics["signal_return"], 6),
        "candidate_signal_relative_vs_spy": _round(metrics["signal_relative_vs_spy"], 6),
        "candidate_close_location": _round(metrics["close_location"], 6),
        "candidate_volume_ratio_20d": _round(metrics["volume_ratio_20d"], 6),
        "candidate_realized_vol_20d": _round(metrics["realized_vol_20d"], 6),
        "candidate_avg_dollar_volume_20d": _round(metrics["adv20"], 2),
        "industry_context": {
            "group_key": metrics["group_key"],
            "liquid_group_count": group["liquid_group_count"],
            "median_ret20_excess_spy": _round(group["median_ret20_excess_spy"], 6),
            "median_ret5_excess_spy": _round(group["median_ret5_excess_spy"], 6),
            "ret20_positive_fraction": _round(group["ret20_positive_fraction"], 6),
            "rule_version": SOURCE_RULE_VERSION,
        },
        "sector": metrics.get("sector"),
        "industry": metrics.get("industry"),
        "sector_coverage_status": metrics.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _select_candidates_for_paper(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    state: dict[str, Any],
    config: dict[str, Any],
    create_trades: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = _trading_dates(rows_by_ticker)
    date_pos = {day: pos for pos, day in enumerate(dates)}
    next_allowed = _cooldown_positions_from_state(
        state=state,
        trading_dates=dates,
        config=config,
    )
    blocked = _blocked_tickers(state)
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
        if ticker in blocked:
            rejected.append({**row, "filter_reason": "pending_or_open_same_ticker"})
            continue
        if used_date_counts[signal_date] >= int(config["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        if pos < next_allowed.get(ticker, -1):
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        if create_trades:
            trade = replay_trade_from_candidate(
                rows_by_ticker=rows_by_ticker,
                candidate=row,
                config=config,
            )
            if trade is None:
                rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
                continue
            selected.append(trade)
        else:
            selected.append(_candidate_for_snapshot(row, config))
        used_date_counts[signal_date] += 1
        next_allowed[ticker] = pos + int(config["same_ticker_cooldown_days"])
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
    idx = _row_index(rows).get(str(candidate.get("date") or "")[:10])
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(cfg["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _value(rows[entry_idx], "open")
    exit_raw = _value(rows[exit_idx], "close")
    if entry_raw is None or exit_raw is None:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(cfg["round_trip_cost_pct"])
    notional = float(cfg["paper_notional_usd"])
    out = {
        **candidate,
        "signal_date": candidate.get("date"),
        "entry_date": _date(rows[entry_idx]),
        "exit_date": _date(rows[exit_idx]),
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": int(cfg["hold_days"]),
        "paper_notional_usd": notional,
        "notional_usd": notional,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "net_return_pct": _round(pnl_pct_net, 6),
        "pnl": _round(notional * pnl_pct_net, 2),
        "paper_status": "closed",
        "decision_id": _decision_id(candidate),
        "trade_enabled": False,
        "alters_orders": False,
    }
    return _safe(out)


def _pending_entry_from_candidate(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = _candidate_for_snapshot(row, config)
    out.update(
        {
            "decision_id": _decision_id(row),
            "signal_date": row.get("signal_date") or row.get("date"),
            "paper_status": "pending_entry",
            "entry_timing": "next_session_open",
            "hold_days": int(config["hold_days"]),
        }
    )
    return out


def _candidate_for_snapshot(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(row)
    out.update(
        {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "paper_notional_usd": float(config["paper_notional_usd"]),
            "notional_usd": float(config["paper_notional_usd"]),
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return _safe(out)


def _advance_paper_state(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    state: dict[str, Any],
    as_of_date: str,
    config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    opened = _fill_pending_entries(state, rows_by_ticker, as_of_date, config)
    closed = _advance_open_positions(state, rows_by_ticker, as_of_date, config)
    return {"opened_this_run": opened, "closed_this_run": closed, "skipped_this_run": []}


def _fill_pending_entries(
    state: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_pending: list[dict[str, Any]] = []
    opened_today: list[dict[str, Any]] = []
    for pending in state.get("pending_entries") or []:
        if not isinstance(pending, dict):
            continue
        ticker = str(pending.get("ticker") or "").upper()
        signal_date = str(pending.get("signal_date") or pending.get("date") or "")[:10]
        rows = rows_by_ticker.get(ticker) or []
        idx = _row_index(rows).get(as_of)
        if idx is None or as_of <= signal_date:
            still_pending.append(pending)
            continue
        open_price = _value(rows[idx], "open")
        if open_price is None:
            still_pending.append(pending)
            continue
        opened = deepcopy(pending)
        opened.update(
            {
                "entry_date": as_of,
                "entry_raw_open": _round(open_price, 4),
                "entry_price": _round(apply_entry_fill(open_price), 4),
                "observed_trading_days": 1,
                "last_observed_date": as_of,
                "paper_status": "open",
            }
        )
        state["open_positions"].append(opened)
        opened_today.append(opened)
    state["pending_entries"] = still_pending
    return opened_today


def _advance_open_positions(
    state: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open: list[dict[str, Any]] = []
    closed_today: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        idx = _row_index(rows).get(as_of)
        if idx is None or as_of < str(position.get("entry_date") or "")[:10]:
            still_open.append(position)
            continue
        working = deepcopy(position)
        if str(working.get("last_observed_date") or "") != as_of:
            working["observed_trading_days"] = int(working.get("observed_trading_days") or 0) + 1
            working["last_observed_date"] = as_of
        if int(working.get("observed_trading_days") or 0) < int(config["hold_days"]):
            still_open.append(working)
            continue
        close_price = _value(rows[idx], "close")
        entry_price = _positive_float(working.get("entry_price"))
        notional = _positive_float(working.get("notional_usd") or working.get("paper_notional_usd"))
        if close_price is None or entry_price is None or notional is None:
            still_open.append(working)
            continue
        exit_price = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
        pnl_pct_net = (exit_price / entry_price) - 1.0 - float(config["round_trip_cost_pct"])
        closed = deepcopy(working)
        closed.update(
            {
                "exit_date": as_of,
                "exit_raw_close": _round(close_price, 4),
                "exit_price": _round(exit_price, 4),
                "pnl_pct_net": _round(pnl_pct_net, 6),
                "net_return_pct": _round(pnl_pct_net, 6),
                "pnl": _round(notional * pnl_pct_net, 2),
                "paper_status": "closed",
            }
        )
        if not _has_closed_decision(state, closed["decision_id"]):
            state["closed_positions"].append(closed)
            closed_today.append(closed)
    state["open_positions"] = still_open
    return closed_today


def _resolve_sector_entries(
    *,
    sector_entries: dict[str, dict[str, Any]] | None,
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    if sector_entries:
        raw_entries = sector_entries
    elif isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("entries"), dict):
        raw_entries = candidate_universe["entries"]
    elif isinstance(candidate_universe, dict) and isinstance(candidate_universe.get("records"), dict):
        raw_entries = candidate_universe["records"]
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


def _normalise_ohlcv_by_ticker(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        str(ticker).upper(): rows
        for ticker, data in payload.items()
        if (rows := _normalise_ohlcv_rows(data))
    }


def _normalise_ohlcv_rows(data: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if data is None:
        return rows
    if hasattr(data, "iterrows"):
        for idx, row in data.iterrows():
            rows.append(_row_from_mapping(row, idx))
    elif isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                rows.append(_row_from_mapping(row, None))
    return sorted([row for row in rows if row.get("date")], key=lambda row: row["date"])


def _row_from_mapping(row: Any, idx: Any) -> dict[str, Any]:
    def pick(*names: str) -> Any:
        for name in names:
            try:
                value = row.get(name)
            except AttributeError:
                value = None
            if value is not None:
                return value
        return None

    return {
        "date": _date10(pick("Date", "date") or idx),
        "open": _float_or_none(pick("Open", "open")),
        "high": _float_or_none(pick("High", "high")),
        "low": _float_or_none(pick("Low", "low")),
        "close": _float_or_none(pick("Close", "close")),
        "volume": _float_or_none(pick("Volume", "volume")),
    }


def _group_key(meta: dict[str, Any]) -> str | None:
    industry = str(meta.get("industry") or "").strip()
    sector = str(meta.get("sector") or "").strip()
    if industry:
        return industry
    if sector:
        return f"Sector:{sector}"
    return None


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("candidate_industry_lag_20d") or 0.0),
        -float(row.get("candidate_signal_relative_vs_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
    )


def _normalise_state(state: dict[str, Any]) -> None:
    for key in ["pending_entries", "open_positions", "closed_positions", "skipped_entries"]:
        if not isinstance(state.get(key), list):
            state[key] = []
    state["schema_version"] = STATE_SCHEMA_VERSION
    state["sleeve"] = SLEEVE_NAME


def _blocked_tickers(state: dict[str, Any]) -> set[str]:
    blocked: set[str] = set()
    for key in ("pending_entries", "open_positions"):
        for row in state.get(key) or []:
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                blocked.add(ticker)
    return blocked


def _cooldown_positions_from_state(
    *,
    state: dict[str, Any],
    trading_dates: list[str],
    config: dict[str, Any],
) -> dict[str, int]:
    date_pos = {day: pos for pos, day in enumerate(trading_dates)}
    cooldown = int(config["same_ticker_cooldown_days"])
    next_allowed: dict[str, int] = {}
    for key in ("closed_positions", "skipped_entries"):
        for row in state.get(key) or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            pos = date_pos.get(signal_date)
            if ticker and pos is not None:
                next_allowed[ticker] = max(next_allowed.get(ticker, -1), pos + cooldown)
    return next_allowed


def _forward_paper_gate(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    pnl_by_ticker: Counter[str] = Counter()
    wins = 0
    for row in closed:
        ticker = str(row.get("ticker") or "").upper()
        pnl = float(row.get("pnl") or 0.0)
        pnl_by_ticker[ticker] += pnl
        if pnl > 0:
            wins += 1
    total_pnl = sum(pnl_by_ticker.values())
    positive = {ticker: pnl for ticker, pnl in pnl_by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_share = (
        max(positive.values()) / positive_total if positive_total > 0 and positive else None
    )
    hhi = (
        sum((pnl / positive_total) ** 2 for pnl in positive.values())
        if positive_total > 0 and positive
        else None
    )
    reasons = []
    if len(closed) < int(config["forward_gate_min_closed_trades"]):
        reasons.append("not_enough_closed_forward_paper_trades")
    if bool(config["forward_gate_positive_net_pnl"]) and total_pnl <= 0.0:
        reasons.append("forward_net_pnl_not_positive")
    if closed and wins / len(closed) < float(config["forward_gate_min_win_rate"]):
        reasons.append("forward_win_rate_too_low")
    if max_share is not None and max_share > float(config["forward_gate_max_single_ticker_positive_share"]):
        reasons.append("forward_positive_pnl_concentration_too_high")
    if hhi is not None and hhi > float(config["forward_gate_max_positive_hhi"]):
        reasons.append("forward_positive_hhi_too_high")
    passed = not reasons
    return {
        "passed": passed,
        "status": "passed" if passed else "blocked",
        "reasons": reasons,
        "closed_trade_count": len(closed),
        "net_pnl": _round(total_pnl, 2),
        "win_rate": _round(wins / len(closed), 6) if closed else None,
        "max_single_ticker_positive_share": _round(max_share, 6) if max_share is not None else None,
        "positive_pnl_hhi": _round(hhi, 6) if hhi is not None else None,
        "trade_enabled_after_gate": False,
    }


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "paper attribution module only; core trading policy unchanged",
        "backtester_adapter_changed": True,
        "run_adapter_changed": True,
        "replay_only": False,
        "default_off_paper_only": True,
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
        "scope": "default_off_industry_relative_laggard_repair_paper_attribution",
    }


def _parameter_summary(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "paper_notional_usd",
        "daily_entry_slots",
        "hold_days",
        "same_ticker_cooldown_days",
        "min_price",
        "min_avg_dollar_volume_20d",
        "group_lookback_days",
        "recent_lookback_days",
        "trend_lookback_days",
        "min_industry_liquid_count",
        "min_group_median_ret20_excess_spy",
        "min_group_ret20_positive_fraction",
        "min_group_median_ret5_excess_spy",
        "min_industry_lag_20d",
        "max_industry_lag_20d",
        "min_candidate_ret20_excess_spy",
        "min_candidate_ret60_excess_spy",
        "min_candidate_ret5_excess_spy",
        "min_signal_return",
        "max_signal_return",
        "min_signal_relative_vs_spy",
        "min_close_location",
        "min_volume_ratio_20d",
        "max_volume_ratio_20d",
        "max_realized_vol_20d",
    ]
    return {key: config[key] for key in keys}


def _candidate_universe_summary(
    candidate_universe: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(candidate_universe, dict):
        count = len(candidate_universe.get("tickers") or candidate_universe.get("entries") or rows_by_ticker)
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


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _decision_id(row: dict[str, Any]) -> str:
    return f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{row.get('date')}:{row.get('ticker')}"


def _decision_ids(state: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for bucket in ("pending_entries", "open_positions", "closed_positions"):
        for row in state.get(bucket) or []:
            decision_id = str(row.get("decision_id") or "")
            if decision_id:
                out.add(decision_id)
    return out


def _has_closed_decision(state: dict[str, Any], decision_id: str) -> bool:
    return any(
        str(row.get("decision_id") or "") == decision_id
        for row in state.get("closed_positions") or []
        if isinstance(row, dict)
    )


def _unrealized_pnl(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    open_positions: list[dict[str, Any]],
    as_of_date: str,
) -> float:
    total = 0.0
    for position in open_positions:
        rows = rows_by_ticker.get(str(position.get("ticker") or "").upper()) or []
        idx = _row_index(rows).get(as_of_date)
        close_price = _value(rows[idx], "close") if idx is not None else None
        entry_price = _positive_float(position.get("entry_price"))
        notional = _positive_float(position.get("notional_usd") or position.get("paper_notional_usd"))
        if close_price is None or entry_price is None or notional is None:
            continue
        total += notional * ((close_price / entry_price) - 1.0)
    return round(total, 2)


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _date(row: dict[str, Any]) -> str:
    return _date10(row.get("date") or row.get("Date"))


def _date10(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key.lower(), row.get(key.capitalize(), row.get(key.upper())))
    if key.lower() == "volume":
        return _nonnegative_float(value)
    return _positive_float(value)


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = _value(rows[idx - 1], "close")
    close = _value(rows[idx], "close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = _value(rows[idx - lookback], "close")
    close = _value(rows[idx], "close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback - 1:
        return None
    values = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = _value(row, "close")
        volume = _value(row, "volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _volume_ratio(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    current = _value(rows[idx], "volume")
    prior = [_value(row, "volume") for row in rows[idx - lookback : idx]]
    if current is None or any(value is None for value in prior):
        return None
    avg = sum(float(value) for value in prior if value is not None) / len(prior)
    if avg <= 0:
        return None
    return current / avg


def _close_location(row: dict[str, Any]) -> float | None:
    high = _value(row, "high")
    low = _value(row, "low")
    close = _value(row, "close")
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


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_float(value: Any) -> float | None:
    number = _float_or_none(value)
    return number if number is not None and number > 0 else None


def _nonnegative_float(value: Any) -> float | None:
    number = _float_or_none(value)
    return number if number is not None and number >= 0 else None


def _round(value: Any, digits: int = 4) -> Any:
    number = _float_or_none(value)
    return round(number, digits) if number is not None else None


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
