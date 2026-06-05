"""Broad Companyfacts peer-confirmed filing-drift adapter candidate.

This shared helper was built for exp-20260605-015 to retest the positive
exp-20260605-014 replay lead with production-realistic chronological semantics.
That promotion failed Gate 4, so the helper is not wired into daily production.
It never emits live orders and must not alter core signal generation, ranking,
sizing, exits, heat, LLM, news, or watchlists.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
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


SLEEVE_NAME = "BROAD_COMPANYFACTS_PEER_CONFIRMED_FILING_DRIFT_PAPER"
RULE_VERSION = "broad_companyfacts_peer_confirmed_filing_drift_shared_adapter_v1"
SOURCE_RULE_VERSION = "broad_companyfacts_peer_confirmed_filing_drift_candidate_source_v1"
REPLACEMENT_VALUE_RULE_VERSION = (
    "broad_companyfacts_peer_confirmed_filing_drift_forward_replacement_value_v1"
)
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "companyfacts_peer_confirmed_filing_drift" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "companyfacts_peer_confirmed_filing_drift"
    / "snapshots.jsonl"
)
DEFAULT_GROWTH_DIR = DATA_ROOT / "kova" / "fundamentals"

EXCLUDED_TICKERS = {
    "ARKX",
    "DIA",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "QQQ",
    "SGOL",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "daily_entry_slots": 1,
    "max_active_positions": 8,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "max_fundamental_age_days": 120,
    "peer_confirmation_lookback_days": 45,
    "min_peer_confirmations": 1,
    "min_revenue_yoy_growth": 0.15,
    "min_profit_yoy_growth": 0.15,
    "min_price": 10.0,
    "min_avg_dollar_volume_20d": 50_000_000.0,
    "min_ret20_excess_spy": 0.0,
    "min_close_location": 0.55,
    "min_volume_ratio_20d": 0.90,
    "same_ticker_cooldown_days": 30,
    "forward_gate_min_closed_trades": 30,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_positive_hhi": 0.30,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_companyfacts_peer_confirmed_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_companyfacts_peer_confirmed_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_companyfacts_peer_confirmed_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_companyfacts_peer_confirmed_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_companyfacts_peer_confirmed_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_companyfacts_peer_confirmed_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_companyfacts_peer_confirmed_paper_sleeve_snapshot(
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
        "companyfacts_growth": {"status": reason, "row_count": 0},
        "peer_confirmation": {
            "rule_version": SOURCE_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "alters_orders": False,
            "candidate_count": 0,
            "min_peer_confirmations": DEFAULT_CONFIG["min_peer_confirmations"],
            "peer_confirmation_lookback_days": DEFAULT_CONFIG[
                "peer_confirmation_lookback_days"
            ],
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_companyfacts_peer_confirmed_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    companyfacts_growth_rows: list[dict[str, Any]] | None = None,
    companyfacts_growth_path: Path | str | None = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_companyfacts_peer_confirmed_paper_sleeve_snapshot(
            as_of_date,
            "missing_ohlcv",
        )
    if "SPY" not in rows_by_ticker:
        return empty_companyfacts_peer_confirmed_paper_sleeve_snapshot(
            as_of_date,
            "missing_spy_ohlcv",
        )

    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    growth_rows, growth_source = _resolve_growth_rows(
        companyfacts_growth_rows=companyfacts_growth_rows,
        companyfacts_growth_path=companyfacts_growth_path,
        max_asof=as_of_date,
    )
    growth_index = build_companyfacts_growth_index(growth_rows)

    working_state = deepcopy(
        state
        if state is not None
        else load_companyfacts_peer_confirmed_paper_state(state_path)
    )
    _normalise_state(working_state)

    exact_current = {
        ticker: rows[idx]["close"]
        for ticker, rows in rows_by_ticker.items()
        for idx in [_index_on_date(rows, as_of_date)]
        if idx is not None and _positive_float(rows[idx].get("close")) is not None
    }
    exact_opens = {
        ticker: rows[idx]["open"]
        for ticker, rows in rows_by_ticker.items()
        for idx in [_index_on_date(rows, as_of_date)]
        if idx is not None and _positive_float(rows[idx].get("open")) is not None
    }
    provided_current = _normalise_prices(current_prices)
    provided_opens = _normalise_prices(open_prices)
    current = {
        **exact_current,
        **{ticker: value for ticker, value in provided_current.items() if ticker in exact_current},
    }
    opens = {
        **exact_opens,
        **{ticker: value for ticker, value in provided_opens.items() if ticker in exact_opens},
    }
    asof_has_benchmark_price = _index_on_date(rows_by_ticker.get("SPY") or [], as_of_date) is not None

    if asof_has_benchmark_price:
        closed_today = _advance_open_positions(
            working_state,
            as_of=as_of_date,
            current_prices=current,
            config=cfg,
        )
        filled_today, skipped_today = _fill_pending_entries(
            working_state,
            as_of=as_of_date,
            open_prices=opens,
            current_prices=current,
            config=cfg,
        )
    else:
        closed_today = []
        filled_today = []
        skipped_today = []

    active_tickers = {
        str(row.get("ticker") or "").upper()
        for row in working_state.get("open_positions") or []
        if isinstance(row, dict)
    }
    pending_tickers = {
        str(row.get("ticker") or "").upper()
        for row in working_state.get("pending_entries") or []
        if isinstance(row, dict)
    }
    last_selected_by_ticker = _last_selected_by_ticker(working_state)
    candidates, rejected, audit = build_companyfacts_peer_confirmed_candidates_for_day(
        as_of=as_of_date,
        ohlcv_by_ticker=rows_by_ticker,
        growth_index=growth_index,
        candidate_universe=universe,
        open_position_tickers=active_tickers,
        pending_tickers=pending_tickers,
        last_selected_by_ticker=last_selected_by_ticker,
        config=cfg,
    )

    room = max(0, int(cfg["max_active_positions"]) - len(working_state.get("open_positions") or []))
    new_pending: list[dict[str, Any]] = []
    if room > 0 and cfg.get("paper_enabled", True):
        capacity = min(room, int(cfg["daily_entry_slots"]))
        for candidate in candidates[:capacity]:
            entry = _pending_entry_from_candidate(candidate, as_of=as_of_date, config=cfg)
            working_state["pending_entries"].append(entry)
            new_pending.append(entry)
    for candidate in candidates[len(new_pending):]:
        rejected.append({**candidate, "reasons": ["daily_top1_or_capacity_limit"]})

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    replacement_value_report = build_companyfacts_peer_confirmed_replacement_value_report(
        candidates=candidates,
        pending_entries=working_state.get("pending_entries") or [],
        open_positions=open_positions,
        closed_positions=closed,
        skipped_entries=working_state.get("skipped_entries") or [],
        config=cfg,
    )
    gate = _forward_paper_gate(closed, cfg)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_live_adapter_pass",
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2),
        "candidate_universe": {
            "status": universe["status"],
            "ticker_count": len(universe["tickers"]),
        },
        "price_data": {
            "asof_date": as_of_date,
            "benchmark_has_exact_asof_ohlcv": asof_has_benchmark_price,
            "exact_close_ticker_count": len(exact_current),
            "exact_open_ticker_count": len(exact_opens),
            "state_transitions_require_exact_asof_ohlcv": True,
        },
        "companyfacts_growth": {
            "status": "ok" if growth_rows else "missing_companyfacts_growth_rows",
            "row_count": len(growth_rows),
            "source_path": growth_source,
        },
        "peer_confirmation": {
            "rule_version": SOURCE_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "alters_orders": False,
            "candidate_count": len(candidates),
            "min_peer_confirmations": int(cfg["min_peer_confirmations"]),
            "peer_confirmation_lookback_days": int(cfg["peer_confirmation_lookback_days"]),
            "peer_rejected_count": audit.get("peer_rejected_count", 0),
            "industry_group_count": audit.get("industry_group_count", 0),
        },
        "forward_paper_gate": gate,
        "replacement_value_report": replacement_value_report,
        "production_impact": _production_impact(),
        "candidate_audit": audit,
        "candidates": candidates,
        "rejected_candidates": rejected[:100],
        "new_pending_entries": new_pending,
        "filled_positions_today": filled_today,
        "closed_positions_today": closed_today,
        "skipped_entries_today": skipped_today,
        "pending_entries": working_state.get("pending_entries") or [],
        "open_positions": open_positions,
        "closed_positions_sample": closed[-20:],
    }

    if persist:
        save_companyfacts_peer_confirmed_paper_state(working_state, state_path)
        append_companyfacts_peer_confirmed_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_companyfacts_growth_index(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    index: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("growth_status") not in (None, "ok"):
            continue
        ticker = str(raw.get("ticker") or "").upper().strip()
        canonical = str(raw.get("canonical") or "").strip()
        asof = _date10(raw.get("asof_date") or raw.get("current_filed") or raw.get("filed"))
        growth = _float_or_none(raw.get("yoy_growth"))
        if not ticker or canonical not in {"revenue", "eps_basic", "eps_diluted", "net_income"}:
            continue
        if not asof or growth is None:
            continue
        index[ticker][canonical].append(
            {
                "ticker": ticker,
                "canonical": canonical,
                "asof_date": asof,
                "yoy_growth": growth,
                "current_value": _float_or_none(raw.get("current_value") or raw.get("value")),
                "prior_value": _float_or_none(raw.get("prior_value")),
                "current_form": raw.get("current_form") or raw.get("form"),
                "current_fy": raw.get("current_fy") or raw.get("fy"),
                "current_fp": raw.get("current_fp") or raw.get("fp"),
                "current_period_end": raw.get("current_period_end") or raw.get("end"),
            }
        )
    for ticker_rows in index.values():
        for facts in ticker_rows.values():
            facts.sort(key=lambda item: item["asof_date"])
    return {ticker: dict(facts) for ticker, facts in index.items()}


def build_companyfacts_peer_confirmed_candidates_for_day(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    open_position_tickers: set[str] | list[str] | None = None,
    pending_tickers: set[str] | list[str] | None = None,
    last_selected_by_ticker: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    sector_lookup, industry_groups, sector_coverage = _load_industry_groups(universe["tickers"])
    blocked = {str(t).upper() for t in (open_position_tickers or [])}
    blocked.update(str(t).upper() for t in (pending_tickers or []))
    last_selected = {str(k).upper(): _date10(v) for k, v in (last_selected_by_ticker or {}).items()}

    day_candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    peer_rejected_count = 0
    for ticker in universe["tickers"]:
        if ticker in EXCLUDED_TICKERS or ticker == "SPY" or ticker in blocked:
            continue
        if _cooldown_active(last_selected.get(ticker), as_of_date, cfg):
            continue
        candidate, reason = _candidate_for_ticker_day(
            ticker=ticker,
            rows=rows_by_ticker.get(ticker) or [],
            spy_rows=rows_by_ticker.get("SPY") or [],
            signal_day=as_of_date,
            growth_index=growth_index,
            sector_lookup=sector_lookup,
            industry_groups=industry_groups,
            config=cfg,
        )
        if candidate is not None:
            day_candidates.append(candidate)
        elif reason == "insufficient_peer_confirmation":
            peer_rejected_count += 1
    day_candidates.sort(key=lambda row: float(row.get("candidate_score") or 0.0), reverse=True)
    selected = day_candidates[:1]
    for row in day_candidates[1:]:
        rejected.append({**row, "reasons": ["daily_top1_or_capacity_limit"]})
    audit = {
        "raw_candidate_count": len(selected),
        "candidate_rows_before_daily_top1": len(day_candidates),
        "peer_rejected_count": peer_rejected_count,
        "growth_ticker_count": len(growth_index),
        "warehouse_frame_count": len(rows_by_ticker),
        "industry_group_count": len(industry_groups),
        "same_ticker_cooldown_days": int(cfg["same_ticker_cooldown_days"]),
        "peer_confirmation_lookback_days": int(cfg["peer_confirmation_lookback_days"]),
        "min_peer_confirmations": int(cfg["min_peer_confirmations"]),
        "sector_coverage": sector_coverage,
    }
    return selected, rejected, audit


def build_companyfacts_peer_confirmed_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    companyfacts_growth_rows: list[dict[str, Any]],
    windows: dict[str, dict[str, str]],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    growth_index = build_companyfacts_growth_index(companyfacts_growth_rows)
    all_tickers = sorted(ticker for ticker in rows_by_ticker if ticker != "SPY")
    universe = {"status": "historical_warehouse_frames", "tickers": all_tickers}
    selected: list[dict[str, Any]] = []
    candidates_by_window: dict[str, int] = defaultdict(int)
    selected_by_window: dict[str, int] = defaultdict(int)
    peer_rejected_by_window: dict[str, int] = defaultdict(int)
    last_selected_by_ticker: dict[str, str] = {}

    for label, window in windows.items():
        for day in _trading_days(rows_by_ticker, window["start"], window["end"]):
            day_selected, _rejected, audit = build_companyfacts_peer_confirmed_candidates_for_day(
                as_of=day,
                ohlcv_by_ticker=rows_by_ticker,
                growth_index=growth_index,
                candidate_universe=universe,
                last_selected_by_ticker=last_selected_by_ticker,
                config=cfg,
            )
            candidates_by_window[label] += int(audit.get("candidate_rows_before_daily_top1") or 0)
            peer_rejected_by_window[label] += int(audit.get("peer_rejected_count") or 0)
            if not day_selected:
                continue
            trade = _candidate_trade_from_selected(
                day_selected[0],
                rows_by_ticker.get(day_selected[0]["ticker"]) or [],
                cfg,
            )
            if trade is None:
                continue
            trade["window"] = label
            selected.append(trade)
            selected_by_window[label] += 1
            last_selected_by_ticker[trade["ticker"]] = str(trade["signal_date"])

    audit = {
        "raw_candidate_count": len(selected),
        "candidate_rows_before_daily_top1_by_window": dict(candidates_by_window),
        "selected_by_window": dict(selected_by_window),
        "peer_rejected_by_window": dict(peer_rejected_by_window),
        "growth_ticker_count": len(growth_index),
        "warehouse_frame_count": len(rows_by_ticker),
        "same_ticker_cooldown_days": int(cfg["same_ticker_cooldown_days"]),
        "peer_confirmation_lookback_days": int(cfg["peer_confirmation_lookback_days"]),
        "min_peer_confirmations": int(cfg["min_peer_confirmations"]),
    }
    return selected, audit


def load_companyfacts_growth_rows(
    *,
    path: Path | str | None = None,
    max_asof: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    source = Path(path) if path is not None else _latest_growth_path()
    if source is None or not source.exists():
        return [], None
    rows: list[dict[str, Any]] = []
    max_day = _date10(max_asof) if max_asof else None
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            asof = _date10(row.get("asof_date") or row.get("current_filed") or row.get("filed"))
            if max_day and asof and asof > max_day:
                continue
            rows.append(row)
    return rows, _repo_rel(source)


def build_companyfacts_peer_confirmed_replacement_value_report(
    *,
    candidates: list[dict[str, Any]],
    pending_entries: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    closed_positions: list[dict[str, Any]],
    skipped_entries: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    closed = closed_positions or []
    by_ticker: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"closed": 0, "pnl": 0.0, "positive_pnl": 0.0}
    )
    for row in closed:
        ticker = str(row.get("ticker") or "").upper()
        pnl = _money(row.get("pnl"))
        by_ticker[ticker]["closed"] += 1
        by_ticker[ticker]["pnl"] = round(by_ticker[ticker]["pnl"] + pnl, 2)
        if pnl > 0:
            by_ticker[ticker]["positive_pnl"] = round(
                by_ticker[ticker]["positive_pnl"] + pnl,
                2,
            )
    positive_total = sum(row["positive_pnl"] for row in by_ticker.values())
    for row in by_ticker.values():
        row["positive_pnl_share"] = (
            round(row["positive_pnl"] / positive_total, 6) if positive_total > 0 else None
        )
    return {
        "rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "read_only": True,
        "trade_enabled": False,
        "alters_orders": False,
        "candidate_count": len(candidates or []),
        "pending_count": len(pending_entries or []),
        "open_count": len(open_positions or []),
        "closed_count": len(closed),
        "skipped_count": len(skipped_entries or []),
        "closed_pnl": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "positive_closed_pnl": round(positive_total, 2),
        "single_ticker_positive_share": _single_ticker_positive_share(closed),
        "positive_pnl_hhi": _positive_pnl_hhi(closed),
        "by_ticker": dict(sorted(by_ticker.items())),
        "config": {
            "paper_notional_usd": float(_config(config)["paper_notional_usd"]),
            "hold_days": int(_config(config)["hold_days"]),
        },
    }


def _resolve_growth_rows(
    *,
    companyfacts_growth_rows: list[dict[str, Any]] | None,
    companyfacts_growth_path: Path | str | None,
    max_asof: str,
) -> tuple[list[dict[str, Any]], str | None]:
    if companyfacts_growth_rows is not None:
        return [dict(row) for row in companyfacts_growth_rows], "provided_rows"
    return load_companyfacts_growth_rows(path=companyfacts_growth_path, max_asof=max_asof)


def _latest_growth_path() -> Path | None:
    if not DEFAULT_GROWTH_DIR.exists():
        return None
    paths = sorted(DEFAULT_GROWTH_DIR.glob("companyfacts_growth_broad_universe_*.jsonl"))
    if not paths:
        paths = sorted(DEFAULT_GROWTH_DIR.glob("companyfacts_growth_*.jsonl"))
    return paths[-1] if paths else None


def _candidate_for_ticker_day(
    *,
    ticker: str,
    rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
    signal_day: str,
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    sector_lookup: dict[str, dict[str, Any]],
    industry_groups: dict[str, list[str]],
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    pos = _index_on_date(rows, signal_day)
    spy_pos = _index_on_date(spy_rows, signal_day)
    if pos is None or spy_pos is None:
        return None, "missing_signal_day_ohlcv"
    if pos < 20 or spy_pos < 20:
        return None, "insufficient_lookback"

    own_growth = _latest_dual_growth(growth_index, ticker, signal_day, config)
    if own_growth is None:
        return None, "missing_own_dual_growth"
    lookup = sector_lookup.get(ticker) or {}
    industry = str(lookup.get("industry") or "").strip()
    if not industry:
        return None, "missing_industry"
    peers = _peer_confirmations(
        growth_index=growth_index,
        ticker=ticker,
        signal_day=signal_day,
        industry=industry,
        industry_groups=industry_groups,
        config=config,
    )
    if len(peers) < int(config["min_peer_confirmations"]):
        return None, "insufficient_peer_confirmation"

    close = _positive_float(rows[pos].get("close"))
    if close is None or close < float(config["min_price"]):
        return None, "price_below_floor"
    adv20 = _avg_dollar_volume(rows, pos)
    if adv20 is None or adv20 < float(config["min_avg_dollar_volume_20d"]):
        return None, "liquidity_below_floor"
    volume_ratio_20d = _volume_ratio(rows, pos)
    if volume_ratio_20d is None or volume_ratio_20d < float(config["min_volume_ratio_20d"]):
        return None, "volume_ratio_below_floor"
    close_location = _close_location(rows, pos)
    if close_location is None or close_location < float(config["min_close_location"]):
        return None, "close_location_below_floor"
    ret20 = _close_return(rows, pos - 20, pos)
    spy_ret20 = _close_return(spy_rows, spy_pos - 20, spy_pos)
    if ret20 is None or spy_ret20 is None:
        return None, "missing_ret20"
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < float(config["min_ret20_excess_spy"]):
        return None, "ret20_excess_spy_below_floor"

    score = _score_candidate(
        own_growth_score=float(own_growth["growth_score"]),
        peer_confirmations=peers,
        ret20_excess_spy=ret20_excess_spy,
        close_location=close_location,
        volume_ratio_20d=volume_ratio_20d,
    )
    revenue = own_growth["revenue"]
    profit = own_growth["profit"]
    return (
        {
            "sleeve": SLEEVE_NAME,
            "source": SLEEVE_NAME,
            "ticker": ticker,
            "signal_date": signal_day,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "trade_enabled": False,
            "alters_orders": False,
            "intended_notional": float(config["paper_notional_usd"]),
            "paper_notional_usd": float(config["paper_notional_usd"]),
            "hold_days": int(config["hold_days"]),
            "companyfacts_revenue_yoy_growth": round(own_growth["revenue_growth"], 6),
            "companyfacts_profit_yoy_growth": round(own_growth["profit_growth"], 6),
            "companyfacts_profit_canonical": profit["canonical"],
            "companyfacts_revenue_asof_date": revenue["asof_date"],
            "companyfacts_profit_asof_date": profit["asof_date"],
            "companyfacts_filing_date": own_growth["filing_date"],
            "companyfacts_filing_age_days": own_growth["filing_age_days"],
            "companyfacts_revenue_form": revenue.get("current_form"),
            "companyfacts_profit_form": profit.get("current_form"),
            "peer_relation_type": "same_industry_recent_dual_growth",
            "peer_relation_key": industry,
            "peer_relation_sector": lookup.get("sector"),
            "peer_relation_rule_version": broad_market_sector_map.RULE_VERSION,
            "peer_confirmation_lookback_days": int(config["peer_confirmation_lookback_days"]),
            "peer_confirmation_count": len(peers),
            "peer_confirmation_tickers": [row["ticker"] for row in peers[:8]],
            "peer_confirmation_score": round(sum(float(row["growth_score"]) for row in peers), 6),
            "peer_confirmations": peers[:8],
            "ret20": round(ret20, 6),
            "spy_ret20": round(spy_ret20, 6),
            "ret20_excess_spy": round(ret20_excess_spy, 6),
            "close_location": round(close_location, 6),
            "avg_dollar_volume_20d": round(adv20, 2),
            "volume_ratio_20d": round(volume_ratio_20d, 6),
            "candidate_score": round(score, 6),
        },
        None,
    )


def _latest_dual_growth(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    revenue = _latest_growth_row(growth_index, ticker, "revenue", signal_day, config)
    profit = _profit_growth_row(growth_index, ticker, signal_day, config)
    if revenue is None or profit is None:
        return None
    revenue_growth = float(revenue["yoy_growth"])
    profit_growth = float(profit["yoy_growth"])
    if revenue_growth < float(config["min_revenue_yoy_growth"]):
        return None
    if profit_growth < float(config["min_profit_yoy_growth"]):
        return None
    if revenue.get("current_value") is None or float(revenue["current_value"]) <= 0.0:
        return None
    filing_date = max(str(revenue["asof_date"]), str(profit["asof_date"]))
    filing_age_days = _days_between(filing_date, signal_day)
    if filing_age_days is None or filing_age_days > int(config["max_fundamental_age_days"]):
        return None
    return {
        "revenue": revenue,
        "profit": profit,
        "revenue_growth": revenue_growth,
        "profit_growth": profit_growth,
        "filing_date": filing_date,
        "filing_age_days": filing_age_days,
        "growth_score": min(max(revenue_growth, -1.0), 1.5)
        + min(max(profit_growth, -1.0), 1.5),
    }


def _latest_growth_row(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    canonical: str,
    signal_day: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rows = growth_index.get(str(ticker).upper(), {}).get(canonical)
    if not rows:
        return None
    best = None
    for row in rows:
        if row["asof_date"] <= signal_day:
            best = row
        else:
            break
    if best is None:
        return None
    age = _days_between(best["asof_date"], signal_day)
    if age is None or age > int(config["max_fundamental_age_days"]):
        return None
    return {**best, "asof_age_days": age}


def _profit_growth_row(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    candidates = [
        row
        for canonical in ("eps_diluted", "eps_basic", "net_income")
        if (row := _latest_growth_row(growth_index, ticker, canonical, signal_day, config))
        is not None
    ]
    candidates = [
        row
        for row in candidates
        if row.get("current_value") is not None
        and float(row["current_value"]) > 0.0
        and row.get("prior_value") is not None
        and float(row["prior_value"]) > 0.0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: float(row["yoy_growth"]))


def _peer_confirmations(
    *,
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day: str,
    industry: str,
    industry_groups: dict[str, list[str]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    peers: list[dict[str, Any]] = []
    for peer_ticker in industry_groups.get(industry, []):
        if peer_ticker == ticker:
            continue
        peer_growth = _latest_dual_growth(growth_index, peer_ticker, signal_day, config)
        if peer_growth is None:
            continue
        if peer_growth["filing_age_days"] > int(config["peer_confirmation_lookback_days"]):
            continue
        peers.append(
            {
                "ticker": peer_ticker,
                "filing_date": peer_growth["filing_date"],
                "filing_age_days": peer_growth["filing_age_days"],
                "revenue_yoy_growth": round(peer_growth["revenue_growth"], 6),
                "profit_yoy_growth": round(peer_growth["profit_growth"], 6),
                "growth_score": round(peer_growth["growth_score"], 6),
            }
        )
    peers.sort(key=lambda row: (row["growth_score"], -row["filing_age_days"]), reverse=True)
    return peers


def _score_candidate(
    *,
    own_growth_score: float,
    peer_confirmations: list[dict[str, Any]],
    ret20_excess_spy: float,
    close_location: float,
    volume_ratio_20d: float,
) -> float:
    peer_count = min(len(peer_confirmations), 4)
    peer_score = sum(float(row["growth_score"]) for row in peer_confirmations[:3])
    return (
        own_growth_score
        + 0.60 * peer_count
        + 0.20 * min(peer_score, 4.5)
        + 3.0 * ret20_excess_spy
        + close_location
        + 0.10 * min(volume_ratio_20d, 3.0)
    )


def _candidate_trade_from_selected(
    candidate: dict[str, Any],
    rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    pos = _index_on_date(rows, candidate["signal_date"])
    if pos is None:
        return None
    entry_pos = pos + 1
    exit_pos = entry_pos + int(config["hold_days"])
    if exit_pos >= len(rows):
        return None
    entry_open = _positive_float(rows[entry_pos].get("open"))
    exit_close = _positive_float(rows[exit_pos].get("close"))
    if entry_open is None or exit_close is None:
        return None
    gross_return = exit_close / entry_open - 1.0
    net_return = gross_return - float(config["round_trip_cost_pct"])
    notional = float(config["paper_notional_usd"])
    trade = deepcopy(candidate)
    trade.update(
        {
            "entry_date": rows[entry_pos]["date"],
            "exit_date": rows[exit_pos]["date"],
            "entry_open": round(entry_open, 4),
            "exit_close": round(exit_close, 4),
            "notional": notional,
            "shares": notional / entry_open,
            "gross_return": round(gross_return, 6),
            "net_return": round(net_return, 6),
            "pnl": round(notional * net_return, 2),
        }
    )
    return trade


def _load_industry_groups(
    tickers: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cache = broad_market_sector_map.load_cache()
    sector_lookup: dict[str, dict[str, Any]] = {}
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for ticker in tickers:
        lookup = broad_market_sector_map.lookup_sector(ticker, cache)
        sector_lookup[ticker] = lookup
        industry = str(lookup.get("industry") or "").strip()
        if lookup.get("status") == broad_market_sector_map.OK_STATUS and industry:
            groups[industry].append(ticker)
    return (
        sector_lookup,
        {key: sorted(values) for key, values in groups.items()},
        broad_market_sector_map.coverage_report(tickers, cache),
    )


def _advance_open_positions(
    state: dict[str, Any],
    *,
    as_of: str,
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open: list[dict[str, Any]] = []
    closed_today: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        current = current_prices.get(ticker)
        if current is None:
            still_open.append(position)
            continue
        observed_days = int(position.get("observed_trading_days") or 0) + 1
        position["observed_trading_days"] = observed_days
        position["last_price"] = current
        position["unrealized_pnl"] = _pnl(
            position.get("entry_price"),
            apply_slippage(current, SLIPPAGE_BPS_TARGET, "sell"),
            position.get("notional"),
            float(config["round_trip_cost_pct"]),
        )
        if observed_days >= int(config["hold_days"]):
            exit_price = apply_slippage(current, SLIPPAGE_BPS_TARGET, "sell")
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_price,
                    "exit_reason": "max_hold_days",
                    "pnl": _pnl(
                        position.get("entry_price"),
                        exit_price,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        exit_price,
                        float(config["round_trip_cost_pct"]),
                    ),
                    "trade_enabled": False,
                }
            )
            closed_today.append(closed)
            state["closed_positions"].append(closed)
        else:
            still_open.append(position)
    state["open_positions"] = still_open
    return closed_today


def _fill_pending_entries(
    state: dict[str, Any],
    *,
    as_of: str,
    open_prices: dict[str, float],
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    still_pending: list[dict[str, Any]] = []
    filled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in sorted(state.get("pending_entries") or [], key=_pending_sort_key):
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker") or "").upper()
        if str(entry.get("created_asof") or "") >= as_of:
            still_pending.append(entry)
            continue
        open_price = open_prices.get(ticker)
        if open_price is None:
            skipped_entry = deepcopy(entry)
            skipped_entry.update(
                {
                    "status": "skipped_missing_next_open",
                    "skipped_asof": as_of,
                    "trade_enabled": False,
                }
            )
            skipped.append(skipped_entry)
            state["skipped_entries"].append(skipped_entry)
            continue
        entry_price = apply_entry_fill(open_price)
        notional = _entry_notional(entry, config)
        candidate = entry.get("candidate") or {}
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": "companyfacts_peer_confirmed_filing_drift_candidate_pool",
            "entry_date": as_of,
            "entry_price": entry_price,
            "decision_close_price": candidate.get("close"),
            "notional": notional,
            "shares": round(notional / entry_price, 6) if entry_price else None,
            "observed_trading_days": 0,
            "hold_days": int(config["hold_days"]),
            "last_price": current_prices.get(ticker),
            "status": "open",
            "candidate": deepcopy(candidate),
            "trade_enabled": False,
        }
        if current_prices.get(ticker) and entry_price:
            position["unrealized_pnl"] = _pnl(
                entry_price,
                apply_slippage(current_prices[ticker], SLIPPAGE_BPS_TARGET, "sell"),
                position["notional"],
                float(config["round_trip_cost_pct"]),
            )
        filled.append(position)
        state["open_positions"].append(position)
    state["pending_entries"] = still_pending
    return filled, skipped


def _pending_entry_from_candidate(
    candidate: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    notional = _positive_float(candidate.get("intended_notional"))
    if notional is None:
        notional = float(config["paper_notional_usd"])
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:{ticker}",
        "sleeve": SLEEVE_NAME,
        "ticker": ticker,
        "created_asof": as_of,
        "status": "pending_next_open",
        "notional": notional,
        "candidate": deepcopy(candidate),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _last_selected_by_ticker(state: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for group in ("pending_entries", "open_positions", "closed_positions"):
        for row in state.get(group) or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
            signal_date = _date10(
                candidate.get("signal_date")
                or row.get("created_asof")
                or row.get("entry_date")
                or row.get("exit_date")
            )
            if ticker and signal_date:
                out[ticker] = max(out.get(ticker, ""), signal_date)
    return out


def _forward_paper_gate(closed_positions: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    realized = round(sum(_money(row.get("pnl")) for row in closed_positions), 2)
    wins = sum(1 for row in closed_positions if _money(row.get("pnl")) > 0)
    win_rate = round(wins / len(closed_positions), 4) if closed_positions else None
    single_share = _single_ticker_positive_share(closed_positions)
    hhi = _positive_pnl_hhi(closed_positions)
    checks = {
        "min_closed_trades": len(closed_positions) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0 if config.get("forward_gate_positive_net_pnl", True) else True,
        "min_win_rate": win_rate is not None and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None
        and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_positive_hhi": hhi is not None and hhi <= float(config["forward_gate_max_positive_hhi"]),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": len(closed_positions),
            "realized_pnl": realized,
            "win_rate": win_rate,
            "single_ticker_positive_share": single_share,
            "positive_pnl_hhi": hhi,
        },
        "trade_enabled_after_gate": False,
    }


def _normalise_candidate_universe(
    value: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(value, list):
        tickers = sorted({str(item).upper() for item in value if item})
        return {"status": "provided", "tickers": tickers, "records": {}}
    if isinstance(value, dict):
        records = value.get("records") if isinstance(value.get("records"), dict) else {}
        tickers = {str(item).upper() for item in value.get("tickers") or [] if item}
        tickers.update(str(key).upper() for key in records)
        return {
            "status": value.get("status") or "provided",
            "path": value.get("path"),
            "tickers": sorted(tickers),
            "records": {str(key).upper(): dict(row or {}) for key, row in records.items() if key},
        }
    return {
        "status": "default_rows_by_ticker",
        "tickers": sorted(ticker for ticker in rows_by_ticker if ticker not in EXCLUDED_TICKERS),
        "records": {},
    }


def _normalise_ohlcv_rows(data: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if data is None:
        return rows
    if hasattr(data, "iterrows"):
        for idx, row in data.iterrows():
            date_value = row.get("Date", idx)
            rows.append(
                {
                    "date": _date10(date_value),
                    "open": _float_or_none(row.get("Open")),
                    "high": _float_or_none(row.get("High")),
                    "low": _float_or_none(row.get("Low")),
                    "close": _float_or_none(row.get("Close")),
                    "volume": _float_or_none(row.get("Volume")),
                }
            )
    elif isinstance(data, list):
        for raw in data:
            if not isinstance(raw, dict):
                continue
            rows.append(
                {
                    "date": _date10(raw.get("Date") or raw.get("date")),
                    "open": _float_or_none(raw.get("Open") or raw.get("open")),
                    "high": _float_or_none(raw.get("High") or raw.get("high")),
                    "low": _float_or_none(raw.get("Low") or raw.get("low")),
                    "close": _float_or_none(raw.get("Close") or raw.get("close")),
                    "volume": _float_or_none(raw.get("Volume") or raw.get("volume")),
                }
            )
    return sorted(
        [row for row in rows if row.get("date") and row.get("close") is not None],
        key=lambda row: row["date"],
    )


def _trading_days(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[str]:
    days: set[str] = set()
    for rows in rows_by_ticker.values():
        for row in rows:
            day = str(row.get("date") or "")[:10]
            if start <= day <= end:
                days.add(day)
    return sorted(days)


def _index_on_date(rows: list[dict[str, Any]], as_of: str) -> int | None:
    target = _date10(as_of)
    for idx, row in enumerate(rows or []):
        if str(row.get("date") or "")[:10] == target:
            return idx
    return None


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = _positive_float(rows[start_idx].get("close"))
    end_close = _positive_float(rows[end_idx].get("close"))
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int = 20) -> float | None:
    start = idx - days + 1
    if start < 0:
        return None
    values = []
    for row in rows[start : idx + 1]:
        close = _positive_float(row.get("close"))
        volume = _positive_float(row.get("volume"))
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values) if len(values) == days else None


def _volume_ratio(rows: list[dict[str, Any]], idx: int, days: int = 20) -> float | None:
    start = idx - days + 1
    if start < 0:
        return None
    values = [_positive_float(row.get("volume")) for row in rows[start : idx + 1]]
    clean = [value for value in values if value is not None]
    if len(clean) != days:
        return None
    avg = sum(clean) / len(clean)
    current = _positive_float(rows[idx].get("volume"))
    if avg <= 0.0 or current is None:
        return None
    return current / avg


def _close_location(rows: list[dict[str, Any]], idx: int) -> float | None:
    high = _positive_float(rows[idx].get("high"))
    low = _positive_float(rows[idx].get("low"))
    close = _positive_float(rows[idx].get("close"))
    if high is None or low is None or close is None:
        return None
    if high <= low:
        return 0.5
    return (close - low) / (high - low)


def _normalise_prices(prices: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, value in (prices or {}).items():
        parsed = _positive_float(value)
        if parsed is not None:
            out[str(ticker).upper()] = parsed
    return out


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_entries", [])


def _config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _cooldown_active(last_signal_date: str | None, as_of: str, config: dict[str, Any]) -> bool:
    if not last_signal_date:
        return False
    days = _days_between(last_signal_date, as_of)
    return days is not None and days < int(config["same_ticker_cooldown_days"])


def _entry_notional(entry: dict[str, Any], config: dict[str, Any]) -> float:
    notional = _positive_float(entry.get("notional"))
    if notional is not None:
        return notional
    candidate = entry.get("candidate") or {}
    candidate_notional = _positive_float(candidate.get("intended_notional"))
    if candidate_notional is not None:
        return candidate_notional
    return float(config["paper_notional_usd"])


def _pnl(entry_price: Any, exit_price: Any, notional: Any, cost_pct: float) -> float:
    entry = _positive_float(entry_price)
    exit_ = _positive_float(exit_price)
    amount = _positive_float(notional)
    if not entry or exit_ is None or amount is None:
        return 0.0
    return round(amount * ((exit_ / entry) - 1.0 - cost_pct), 2)


def _return_pct(entry_price: Any, exit_price: Any, cost_pct: float) -> float:
    entry = _positive_float(entry_price)
    exit_ = _positive_float(exit_price)
    if not entry or exit_ is None:
        return 0.0
    return round((exit_ / entry) - 1.0 - cost_pct, 6)


def _single_ticker_positive_share(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    for row in rows:
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(max(by_ticker.values()) / total, 6)


def _positive_pnl_hhi(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    for row in rows:
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(sum((value / total) ** 2 for value in by_ticker.values()), 6)


def _pending_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("created_asof") or ""), str(row.get("ticker") or ""))


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": False,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "replay_only": True,
        "default_off_paper_only": False,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "rejected_broad_companyfacts_peer_confirmed_filing_drift_adapter_candidate",
    }


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(DATA_ROOT.parent.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def _money(value: Any) -> float:
    parsed = _float_or_none(value)
    return parsed if parsed is not None else 0.0


def _positive_float(value: Any) -> float | None:
    parsed = _float_or_none(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _date10(value: Any) -> str:
    if value is None:
        return ""
    return str(value)[:10]


def _days_between(start: Any, end: Any) -> int | None:
    start_text = _date10(start)
    end_text = _date10(end)
    if not start_text or not end_text:
        return None
    try:
        start_day = datetime.fromisoformat(start_text)
        end_day = datetime.fromisoformat(end_text)
    except ValueError:
        return None
    if start_day > end_day:
        return None
    return (end_day - start_day).days
