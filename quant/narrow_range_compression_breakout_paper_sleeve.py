"""Default-off narrow-range compression breakout paper sleeve.

Shared helper for the positive exp-20260608-012 replay lead. Liquid
sector-known stocks that compress into a narrow prior range, then expand range
on the signal day with volume and a high close, become next-open paper
candidates with a fixed 10-trading-day hold.

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
from statistics import median
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


SLEEVE_NAME = "NARROW_RANGE_COMPRESSION_BREAKOUT_PAPER"
RULE_VERSION = "narrow_range_compression_breakout_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "narrow_range_compression_breakout_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "narrow_range_compression_breakout" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "narrow_range_compression_breakout" / "snapshots.jsonl"
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
    "compression_lookback_days": 10,
    "reference_range_lookback_days": 40,
    "max_prior_median_range10_pct": 0.040,
    "max_range10_to_range40_ratio": 0.72,
    "min_signal_range_pct": 0.025,
    "min_signal_range_expansion_vs_10d": 1.55,
    "min_signal_return": 0.003,
    "min_close_location": 0.72,
    "min_volume_ratio_20d": 1.20,
    "min_ret20_excess_spy": 0.000,
    "min_ret60_excess_spy": -0.020,
    "min_ret5": -0.025,
    "max_ret5": 0.110,
    "max_ret20": 0.280,
    "max_realized_vol_20d": 0.065,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_narrow_range_compression_breakout_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_narrow_range_compression_breakout_snapshot(
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
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "narrow_range_compression_breakout_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_narrow_range_compression_breakout_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_narrow_range_compression_breakout_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_narrow_range_compression_breakout_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_narrow_range_compression_breakout_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_narrow_range_compression_breakout_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def build_narrow_range_compression_breakout_snapshot(
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
        state
        if state is not None
        else load_narrow_range_compression_breakout_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_narrow_range_compression_breakout_snapshot(as_of_date, "missing_ohlcv")
    if "SPY" not in rows_by_ticker:
        return empty_narrow_range_compression_breakout_snapshot(
            as_of_date,
            "missing_spy_ohlcv",
        )

    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    if not sector_map:
        return empty_narrow_range_compression_breakout_snapshot(
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
    candidates, contexts, scan = build_narrow_range_compression_breakout_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        sector_entries=sector_map,
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
    )
    selected_rows, rejected = select_narrow_range_compression_breakout_signal_rows(
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
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_compression_breakout_context"))
    elif not selected_rows and contexts and not candidates:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_compression_breakout_candidate"))

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
        save_narrow_range_compression_breakout_state(working_state, state_path)
        append_narrow_range_compression_breakout_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_narrow_range_compression_breakout_historical_trades(
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
        candidates, contexts, scan = build_narrow_range_compression_breakout_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_map,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
        )
        selected, rejected = select_narrow_range_compression_breakout_paper_trades(
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


def build_narrow_range_compression_breakout_candidate_rows(
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
        "days_with_raw_compression_breakout_candidates": 0,
        "raw_compression_breakout_candidates": 0,
    }
    for signal_date in dates:
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = _candidate_for_ticker(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                config=cfg,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            day_rows.append(row)
            candidate_tickers.add(ticker)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_compression_breakout_candidates"] += 1
        scan["raw_compression_breakout_candidates"] += len(day_rows)
        top = day_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_range_expansion_ratio": top[
                    "candidate_range_expansion_ratio"
                ],
                "top_candidate_range10_to_range40_ratio": top[
                    "candidate_range10_to_range40_ratio"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "rule_version": SOURCE_RULE_VERSION,
            }
        )
    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    scan.update(
        {
            "unique_candidate_tickers": len(candidate_tickers),
            **_parameter_summary(cfg),
        }
    )
    return candidates, contexts, scan


def select_narrow_range_compression_breakout_signal_rows(
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
        candidate = {
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
        selected.append(candidate)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    return selected, rejected


def select_narrow_range_compression_breakout_paper_trades(
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


def _candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < int(config["reference_range_lookback_days"]) or spy_idx < 60:
        return None

    close = leader._positive_float(rows[idx].get("close"))
    if close is None or close < float(config["min_price"]):
        return None
    adv20 = leader._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None

    signal_range_pct = _range_pct(rows[idx])
    prior_range10_pct = _median_range_pct(
        rows,
        idx,
        int(config["compression_lookback_days"]),
    )
    prior_range40_pct = _median_range_pct(
        rows,
        idx,
        int(config["reference_range_lookback_days"]),
    )
    signal_return = leader._daily_return(rows, idx)
    close_location = leader._close_location(rows[idx])
    volume_ratio = leader._volume_ratio(rows, idx)
    ret5 = leader._ret(rows, idx, 5)
    ret20 = leader._ret(rows, idx, 20)
    ret60 = leader._ret(rows, idx, 60)
    spy_ret20 = leader._ret(spy_rows, spy_idx, 20)
    spy_ret60 = leader._ret(spy_rows, spy_idx, 60)
    realized_vol20 = leader._realized_vol(rows, idx, 20)
    required = [
        signal_range_pct,
        prior_range10_pct,
        prior_range40_pct,
        signal_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert signal_range_pct is not None
    assert prior_range10_pct is not None
    assert prior_range40_pct is not None
    assert signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    if prior_range10_pct <= 0 or prior_range40_pct <= 0:
        return None

    range_compression_ratio = prior_range10_pct / prior_range40_pct
    range_expansion_ratio = signal_range_pct / prior_range10_pct
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if prior_range10_pct > float(config["max_prior_median_range10_pct"]):
        return None
    if range_compression_ratio > float(config["max_range10_to_range40_ratio"]):
        return None
    if signal_range_pct < float(config["min_signal_range_pct"]):
        return None
    if range_expansion_ratio < float(config["min_signal_range_expansion_vs_10d"]):
        return None
    if signal_return < float(config["min_signal_return"]):
        return None
    if close_location < float(config["min_close_location"]):
        return None
    if volume_ratio < float(config["min_volume_ratio_20d"]):
        return None
    if ret20_excess_spy < float(config["min_ret20_excess_spy"]):
        return None
    if ret60_excess_spy < float(config["min_ret60_excess_spy"]):
        return None
    if ret5 < float(config["min_ret5"]) or ret5 > float(config["max_ret5"]):
        return None
    if ret20 > float(config["max_ret20"]):
        return None
    if realized_vol20 > float(config["max_realized_vol_20d"]):
        return None

    sector_meta = sector_entries[ticker]
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        0.75 * range_expansion_ratio
        + 1.30 * ret20_excess_spy
        + 0.45 * ret60_excess_spy
        + 1.20 * signal_return
        + 0.35 * close_location
        + 0.12 * min(volume_ratio, 4.0)
        + 0.04 * liquidity_score
        - 1.10 * prior_range10_pct
        - 0.75 * realized_vol20
        - 0.25 * max(ret5, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": SLEEVE_NAME,
        "candidate_score": leader._round(score, 6),
        "candidate_signal_range_pct": leader._round(signal_range_pct, 6),
        "candidate_prior_range10_median_pct": leader._round(prior_range10_pct, 6),
        "candidate_prior_range40_median_pct": leader._round(prior_range40_pct, 6),
        "candidate_range10_to_range40_ratio": leader._round(range_compression_ratio, 6),
        "candidate_range_expansion_ratio": leader._round(range_expansion_ratio, 6),
        "candidate_signal_day_return": leader._round(signal_return, 6),
        "candidate_close_location": leader._round(close_location, 6),
        "candidate_volume_ratio_20d": leader._round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": leader._round(adv20, 2),
        "candidate_ret5": leader._round(ret5, 6),
        "candidate_ret20": leader._round(ret20, 6),
        "candidate_spy_ret20": leader._round(spy_ret20, 6),
        "candidate_ret20_excess_spy": leader._round(ret20_excess_spy, 6),
        "candidate_ret60": leader._round(ret60, 6),
        "candidate_spy_ret60": leader._round(spy_ret60, 6),
        "candidate_ret60_excess_spy": leader._round(ret60_excess_spy, 6),
        "candidate_realized_vol_20d": leader._round(realized_vol20, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status")
        or sector_meta.get("status"),
        "rule_version": SOURCE_RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "alters_orders": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


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
        "narrow_range_compression_breakout_context": {
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
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_days", [])


def _state_cooldown_map(
    *,
    existing_state: dict[str, Any] | None,
    date_pos: dict[str, int],
    config: dict[str, Any],
) -> dict[str, int]:
    next_allowed_pos_by_ticker: dict[str, int] = {}
    if not existing_state:
        return next_allowed_pos_by_ticker
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
        -float(row.get("candidate_range_expansion_ratio") or 0.0),
        -float(row.get("candidate_ret20_excess_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("sector") or ""),
        str(row.get("ticker") or ""),
    )


def _range_pct(row: dict[str, Any]) -> float | None:
    high = leader._positive_float(row.get("high"))
    low = leader._positive_float(row.get("low"))
    close = leader._positive_float(row.get("close"))
    if high is None or low is None or close is None or close <= 0:
        return None
    if high < low:
        return None
    return (high - low) / close


def _median_range_pct(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    values = [_range_pct(row) for row in rows[idx - lookback : idx]]
    if any(value is None for value in values):
        return None
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return None
    return median(ordered)


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
        "compression_lookback_days",
        "reference_range_lookback_days",
        "max_prior_median_range10_pct",
        "max_range10_to_range40_ratio",
        "min_signal_range_pct",
        "min_signal_range_expansion_vs_10d",
        "min_signal_return",
        "min_close_location",
        "min_volume_ratio_20d",
        "min_ret20_excess_spy",
        "min_ret60_excess_spy",
        "min_ret5",
        "max_ret5",
        "max_ret20",
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


def prep_and_build_narrow_range_compression_breakout_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict,
    broad_market_candidate_universe: dict,
    spy_ohlcv=None,
    core_entries=None,
):
    if not broad_market_candidate_universe.get("tickers"):
        return empty_narrow_range_compression_breakout_snapshot(
            as_of, "broad_market_candidate_universe_unavailable")
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    return build_narrow_range_compression_breakout_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv,
        candidate_universe=broad_market_candidate_universe,
        core_entries=core_entries,
    )


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "paper attribution module only; core trading policy unchanged",
        "backtester_adapter_changed": True,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": True,
        "daily_snapshot_note": "helper API emits default-off snapshots; run.py wiring is intentionally unchanged in this experiment",
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
        "scope": "default_off_narrow_range_compression_breakout_paper_attribution",
    }
