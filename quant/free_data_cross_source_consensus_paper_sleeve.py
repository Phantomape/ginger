"""Default-off accepted free-data cross-source consensus paper sleeve.

This adapter promotes the positive exp-20260531-030 replay lead into a shared
production-visible observation boundary. It admits a paper candidate only when
at least two independent accepted free-data source families select the same
ticker on the same signal date. It never emits live orders or changes core
signal generation, ranking, sizing, exits, heat, LLM, or news behavior.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from alpha_score_market_regime_paper_sleeve import (
        _date10,
        _exact_asof_price_maps,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _positive_float,
        _return_pct,
        _safe,
        _single_ticker_positive_share,
    )
    from constants import MAX_POSITIONS, ROUND_TRIP_COST_PCT
    from data_paths import data_artifact_path
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.alpha_score_market_regime_paper_sleeve import (
        _date10,
        _exact_asof_price_maps,
        _money,
        _normalise_ohlcv_rows,
        _pnl,
        _positive_float,
        _return_pct,
        _safe,
        _single_ticker_positive_share,
    )
    from quant.constants import MAX_POSITIONS, ROUND_TRIP_COST_PCT
    from quant.data_paths import data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage


SLEEVE_NAME = "ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER"
RULE_VERSION = "accepted_free_data_cross_source_consensus_shared_v1"
CONSENSUS_RULE_VERSION = (
    "accepted_free_data_cross_source_consensus_independent_source_family_v1"
)
LAGGED_CONSENSUS_RULE_VERSION = (
    "accepted_free_data_cross_source_consensus_lagged_independent_source_family_v1"
)
CORE_CAPACITY_RULE_VERSION = "accepted_free_data_consensus_core_capacity_available_gate_v1"
REPLACEMENT_VALUE_RULE_VERSION = (
    "accepted_free_data_cross_source_consensus_forward_replacement_value_v1"
)
SOURCE_FAMILY_RULE_VERSION = "accepted_free_data_consensus_source_family_map_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("free_data_cross_source_consensus_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path(
    "free_data_cross_source_consensus_paper_snapshots"
)

ACCEPTED_SOURCE_NAMES = {
    "ALPHA_SCORE_MARKET_REGIME_PAPER",
    "FINRA_BORROW_PRESSURE_PAPER",
    "FINRA_IWM_CONFIRMED_PAPER",
    "FUNDAMENTAL_GROWTH_RS_PAPER",
    "VOLUME_BREADTH_BREAKOUT_PAPER",
}

SOURCE_FAMILIES = {
    "ALPHA_SCORE_MARKET_REGIME_PAPER": "alpha_score_market_regime",
    "FINRA_BORROW_PRESSURE_PAPER": "finra_short_pressure",
    "FINRA_IWM_CONFIRMED_PAPER": "finra_short_pressure",
    "FUNDAMENTAL_GROWTH_RS_PAPER": "companyfacts_growth_quality",
    "VOLUME_BREADTH_BREAKOUT_PAPER": "volume_breadth_breakout",
}

SOURCE_SNAPSHOT_HISTORY_ARTIFACTS = {
    "ALPHA_SCORE_MARKET_REGIME_PAPER": "alpha_score_market_regime_paper_snapshots",
    "FINRA_IWM_CONFIRMED_PAPER": "finra_iwm_paper_snapshots",
    "FUNDAMENTAL_GROWTH_RS_PAPER": "fundamental_growth_rs_paper_snapshots",
    "VOLUME_BREADTH_BREAKOUT_PAPER": "volume_breadth_breakout_paper_snapshots",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "baseline_paper_notional_usd": 10_000.0,
    "min_source_count": 2,
    "min_source_family_count": 2,
    "source_families": dict(SOURCE_FAMILIES),
    "daily_entry_slots": 1,
    "max_active_positions": 5,
    "hold_days": 10,
    "same_ticker_cooldown_days": 7,
    "source_history_enabled": True,
    "prior_confirmation_trading_days": 3,
    "accepted_source_names": sorted(ACCEPTED_SOURCE_NAMES),
    "require_core_capacity_available": True,
    "max_core_positions": MAX_POSITIONS,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 20,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_pnl_hhi": 0.30,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_free_data_cross_source_consensus_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_free_data_cross_source_consensus_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_free_data_cross_source_consensus_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_free_data_cross_source_consensus_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_free_data_cross_source_consensus_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_free_data_cross_source_consensus_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_free_data_cross_source_consensus_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "consensus_rule_version": CONSENSUS_RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "rejected_candidate_count": 0,
        "source_consensus_key_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "source_consensus": {
            "enabled": True,
            "supported_candidate_count": 0,
            "source_counts": {},
            "source_family_counts": {},
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_free_data_cross_source_consensus_paper_sleeve_snapshot(
    *,
    as_of: str,
    source_snapshots: list[dict[str, Any]] | None = None,
    source_snapshot_history: list[dict[str, Any]] | None = None,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    core_active_position_count: int | None = None,
    max_core_positions: int | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    if not source_snapshots:
        return empty_free_data_cross_source_consensus_paper_sleeve_snapshot(
            as_of_date,
            "missing_source_snapshots",
        )

    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_free_data_cross_source_consensus_paper_sleeve_snapshot(
            as_of_date,
            "missing_ohlcv",
        )

    working_state = deepcopy(
        state
        if state is not None
        else load_free_data_cross_source_consensus_paper_state(state_path)
    )
    _normalise_state(working_state)

    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
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
    trading_dates = _trading_dates_from_rows(rows_by_ticker, as_of_date)
    history_signal_dates = _prior_confirmation_dates(
        trading_dates,
        as_of=as_of_date,
        prior_trading_days=int(cfg["prior_confirmation_trading_days"]),
    )
    if source_snapshot_history is None and persist and cfg.get("source_history_enabled", True):
        source_snapshot_history = load_free_data_cross_source_consensus_source_snapshot_history(
            as_of=as_of_date,
            trading_dates=trading_dates,
            config=cfg,
        )
    current_source_rows_by_key = _source_rows_by_key(
        source_snapshots,
        as_of=as_of_date,
        valid_signal_dates={as_of_date},
        config=cfg,
    )
    history_source_rows_by_key = _source_rows_by_key(
        [*(source_snapshot_history or []), *(source_snapshots or [])],
        as_of=as_of_date,
        valid_signal_dates=set(history_signal_dates),
        config=cfg,
    )
    candidates, rejected, cooldown_summary = _consensus_candidates(
        current_source_rows_by_key,
        history_source_rows_by_key=history_source_rows_by_key,
        history_signal_dates=history_signal_dates,
        as_of=as_of_date,
        active_tickers=active_tickers,
        pending_tickers=pending_tickers,
        state=working_state,
        core_active_position_count=core_active_position_count,
        max_core_positions=max_core_positions,
        config=cfg,
    )

    open_positions = working_state.get("open_positions") or []
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))
    new_pending = []
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
    source_summary = _source_consensus_summary(
        candidates,
        current_source_rows_by_key,
        cfg,
        history_source_rows_by_key=history_source_rows_by_key,
        history_signal_dates=history_signal_dates,
    )
    replacement_value_report = build_free_data_cross_source_consensus_replacement_value_report(
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
        "consensus_rule_version": CONSENSUS_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_activation_review",
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "source_consensus_key_count": len(current_source_rows_by_key),
        "source_consensus_history_key_count": len(history_source_rows_by_key),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(
            sum(_money(row.get("unrealized_pnl")) for row in open_positions),
            2,
        ),
        "source_consensus": source_summary,
        "lagged_source_consensus": _lagged_source_consensus_summary(
            candidates,
            current_source_rows_by_key=current_source_rows_by_key,
            history_source_rows_by_key=history_source_rows_by_key,
            history_signal_dates=history_signal_dates,
            config=cfg,
        ),
        "core_capacity_gate": _core_capacity_gate_summary(
            core_active_position_count=core_active_position_count,
            max_core_positions=max_core_positions,
            config=cfg,
        ),
        "same_ticker_cooldown": cooldown_summary,
        "candidates": deepcopy(candidates),
        "rejected_candidates": deepcopy(rejected[:50]),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "pending_entries": deepcopy(working_state["pending_entries"]),
        "open_positions": deepcopy(open_positions),
        "closed_positions": deepcopy(closed),
        "skipped_entries_today": deepcopy(skipped_today),
        "replacement_value_report": replacement_value_report,
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_replacement_value_no_orders",
    }

    if persist:
        save_free_data_cross_source_consensus_paper_state(working_state, state_path)
        append_free_data_cross_source_consensus_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_free_data_cross_source_consensus_replacement_value_report(
    *,
    candidates: list[dict[str, Any]],
    pending_entries: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    closed_positions: list[dict[str, Any]],
    skipped_entries: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    closed = [row for row in closed_positions or [] if isinstance(row, dict)]
    open_rows = [row for row in open_positions or [] if isinstance(row, dict)]
    pending = [row for row in pending_entries or [] if isinstance(row, dict)]
    skipped = [row for row in skipped_entries or [] if isinstance(row, dict)]
    positive_closed = [row for row in closed if _money(row.get("pnl")) > 0.0]
    positive_pnl = round(sum(_money(row.get("pnl")) for row in positive_closed), 2)
    by_ticker: dict[str, dict[str, Any]] = {}
    for bucket, rows in (
        ("candidate", candidates or []),
        ("pending", pending),
        ("open", open_rows),
        ("closed", closed),
        ("skipped", skipped),
    ):
        for row in rows:
            ticker = _row_ticker(row)
            if not ticker:
                continue
            rec = by_ticker.setdefault(
                ticker,
                {
                    "candidate_count": 0,
                    "pending_count": 0,
                    "open_count": 0,
                    "closed_count": 0,
                    "skipped_count": 0,
                    "closed_pnl": 0.0,
                    "positive_closed_pnl": 0.0,
                },
            )
            rec[f"{bucket}_count"] += 1
            if bucket == "closed":
                pnl = _money(row.get("pnl"))
                rec["closed_pnl"] = round(float(rec["closed_pnl"]) + pnl, 2)
                if pnl > 0:
                    rec["positive_closed_pnl"] = round(
                        float(rec["positive_closed_pnl"]) + pnl,
                        2,
                    )
    for rec in by_ticker.values():
        rec["positive_pnl_share"] = (
            round(float(rec.get("positive_closed_pnl") or 0.0) / positive_pnl, 4)
            if positive_pnl > 0
            else None
        )
    return {
        "schema_version": 1,
        "rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "read_only": True,
        "forward_outcome_horizon_days": int(cfg["hold_days"]),
        "displaced_resource_default": "paper_cash_slot",
        "candidate_count": len(candidates or []),
        "pending_count": len(pending),
        "open_count": len(open_rows),
        "closed_count": len(closed),
        "skipped_count": len(skipped),
        "closed_pnl": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "open_unrealized_pnl": round(
            sum(_money(row.get("unrealized_pnl")) for row in open_rows),
            2,
        ),
        "positive_closed_pnl": positive_pnl,
        "positive_pnl_hhi": _positive_pnl_hhi(closed),
        "top_ticker_positive_pnl_share": _single_ticker_positive_share(closed),
        "by_ticker": dict(sorted(by_ticker.items())),
        "promotion_blockers": [
            blocker
            for blocker in (
                "needs_closed_forward_outcomes"
                if len(closed) < int(cfg["forward_gate_min_closed_trades"])
                else None,
                "needs_replacement_value_vs_core_or_cash",
            )
            if blocker
        ],
        "trade_enabled": False,
        "alters_orders": False,
    }


def _source_rows_by_key(
    source_snapshots: list[dict[str, Any]],
    *,
    as_of: str,
    valid_signal_dates: set[str],
    config: dict[str, Any],
) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    allowed = {str(name).upper() for name in config.get("accepted_source_names") or []}
    rows_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    valid_dates = {_date10(value) for value in valid_signal_dates or set()}
    for snapshot in source_snapshots or []:
        if not isinstance(snapshot, dict):
            continue
        source_name = str(snapshot.get("sleeve") or "").upper()
        if source_name not in allowed:
            continue
        snapshot_asof = _date10(snapshot.get("asof_date") or as_of)
        for candidate in snapshot.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            ticker = str(candidate.get("ticker") or "").upper()
            signal_date = _date10(
                candidate.get("signal_date")
                or candidate.get("date")
                or candidate.get("created_asof")
                or snapshot_asof
            )
            if not ticker or signal_date not in valid_dates or signal_date > as_of:
                continue
            key = (signal_date, ticker)
            candidate_summary = dict(candidate)
            candidate_summary.setdefault("signal_date", signal_date)
            candidate_summary.setdefault("date", signal_date)
            rows_by_key.setdefault(key, {})[source_name] = _source_row_summary(
                source_name,
                candidate_summary,
            )
    return rows_by_key


def _source_row_summary(source_name: str, row: dict[str, Any]) -> dict[str, Any]:
    signal_date = _date10(row.get("signal_date") or row.get("date"))
    summary = {
        "source_name": source_name,
        "ticker": str(row.get("ticker") or "").upper(),
        "date": signal_date,
        "signal_date": signal_date,
        "rule_version": row.get("rule_version"),
    }
    for key in (
        "alpha_score",
        "fundamental_growth_rs_score",
        "volume_breadth_breakout_score",
        "candidate_selection_score",
        "close",
        "paper_notional_usd",
        "intended_notional",
    ):
        if key in row:
            summary[key] = row.get(key)
    return summary


def _consensus_candidates(
    current_source_rows_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]],
    *,
    history_source_rows_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]],
    history_signal_dates: list[str],
    as_of: str,
    active_tickers: set[str],
    pending_tickers: set[str],
    state: dict[str, Any],
    core_active_position_count: int | None,
    max_core_positions: int | None,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    cooldown_rejected = 0
    min_source_count = int(config["min_source_count"])
    min_source_family_count = int(config["min_source_family_count"])
    capacity = _core_capacity_context(
        core_active_position_count=core_active_position_count,
        max_core_positions=max_core_positions,
        config=config,
    )
    for (signal_date, ticker), current_source_rows in sorted(current_source_rows_by_key.items()):
        source_rows = _lagged_source_rows_for_ticker(
            ticker=ticker,
            as_of=signal_date,
            history_signal_dates=history_signal_dates,
            history_source_rows_by_key=history_source_rows_by_key,
            config=config,
        )
        if not source_rows:
            source_rows = [
                _source_row_with_timing(row, as_of=signal_date, config=config)
                for row in current_source_rows.values()
            ]
        source_names = sorted({str(row.get("source_name") or "").upper() for row in source_rows})
        base = _candidate_from_sources(signal_date, ticker, source_rows, current_source_rows, config)
        base.update(_candidate_capacity_fields(capacity))
        if len(source_names) < min_source_count:
            rejected.append({**base, "reasons": ["insufficient_source_count"]})
            continue
        if int(base.get("source_family_count") or 0) < min_source_family_count:
            rejected.append({**base, "reasons": ["insufficient_source_family_count"]})
            continue
        if capacity["required"] and not capacity["known"]:
            rejected.append({**base, "reasons": ["missing_core_capacity_context"]})
            continue
        if capacity["required"] and not capacity["available"]:
            rejected.append({**base, "reasons": ["core_capacity_full"]})
            continue
        if ticker in active_tickers or ticker in pending_tickers:
            rejected.append({**base, "reasons": ["already_pending_or_open"]})
            continue
        last_selected = _last_selected_date(state, ticker)
        if _within_cooldown(as_of, last_selected, int(config["same_ticker_cooldown_days"])):
            cooldown_rejected += 1
            rejected.append(
                {
                    **base,
                    "last_selected_date": last_selected,
                    "reasons": ["same_ticker_cooldown"],
                }
            )
            continue
        candidates.append(base)
    candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or ""),
            -int(row.get("source_family_count") or 0),
            -int(row.get("current_source_family_count") or 0),
            -int(row.get("source_count") or 0),
            0 if row.get("has_lagged_independent_confirmation") else 1,
            "+".join(row.get("source_families") or []),
            "+".join(row.get("current_source_names") or []),
            str(row.get("ticker") or ""),
        )
    )
    cooldown_summary = {
        "rule_version": CONSENSUS_RULE_VERSION,
        "cooldown_days": int(config["same_ticker_cooldown_days"]),
        "rejected_count": cooldown_rejected,
        "trade_enabled": False,
        "alters_orders": False,
    }
    return candidates, rejected, cooldown_summary


def _candidate_from_sources(
    signal_date: str,
    ticker: str,
    source_rows: list[dict[str, Any]],
    current_source_rows: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    source_names = sorted(
        {
            str(row.get("source_name") or "").upper()
            for row in source_rows
            if row.get("source_name")
        }
    )
    source_families = sorted({_source_family(name, config) for name in source_names})
    current_source_names = sorted(current_source_rows)
    current_source_families = sorted(
        {_source_family(name, config) for name in current_source_names}
    )
    prior_rows = [row for row in source_rows if row.get("timing_role") == "prior_confirmation"]
    prior_source_names = sorted(
        {
            str(row.get("source_name") or "").upper()
            for row in prior_rows
            if row.get("source_name")
        }
    )
    prior_families = sorted({_source_family(name, config) for name in prior_source_names})
    has_lagged_independent_confirmation = any(
        family not in set(current_source_families) for family in prior_families
    )
    source_family_map: dict[str, list[str]] = {}
    for source_name in source_names:
        source_family_map.setdefault(_source_family(source_name, config), []).append(source_name)
    notional = float(config["paper_notional_usd"])
    baseline = float(config["baseline_paper_notional_usd"])
    return {
        "ticker": ticker,
        "date": signal_date,
        "signal_date": signal_date,
        "strategy": "accepted_free_data_cross_source_consensus_candidate_pool",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "consensus_rule_version": CONSENSUS_RULE_VERSION,
        "candidate_pool_rule_version": CONSENSUS_RULE_VERSION,
        "cross_source_consensus_candidate_pool": True,
        "source_count": len(source_names),
        "source_family_count": len(source_families),
        "current_source_count": len(current_source_names),
        "current_source_family_count": len(current_source_families),
        "prior_confirmation_source_count": len(prior_source_names),
        "prior_confirmation_family_count": len(prior_families),
        "has_lagged_independent_confirmation": has_lagged_independent_confirmation,
        "source_names": source_names,
        "source_families": source_families,
        "current_source_names": current_source_names,
        "current_source_families": current_source_families,
        "prior_confirmation_source_families": prior_families,
        "source_family_map": {
            family: sorted(names) for family, names in sorted(source_family_map.items())
        },
        "source_rows": sorted(
            deepcopy(source_rows),
            key=lambda row: (
                int(row.get("confirmation_lag_trading_days") or 0),
                str(row.get("source_name") or ""),
            ),
        ),
        "primary_source": source_names[0] if source_names else None,
        "primary_source_family": source_families[0] if source_families else None,
        "paper_notional_usd": notional,
        "intended_notional": notional,
        "safe_paper_notional_usd": notional,
        "baseline_safe_paper_notional_usd": baseline,
        "safe_notional_scalar": round(notional / baseline, 6) if baseline else None,
        "source_agreement_rule": (
            "current_ticker_selected_by_accepted_source_and_confirmed_by_same_day_or_prior_3_trading_day_independent_accepted_source_family"
        ),
        "source_family_rule_version": SOURCE_FAMILY_RULE_VERSION,
        "lagged_consensus_rule_version": LAGGED_CONSENSUS_RULE_VERSION,
        "prior_confirmation_trading_days": int(config["prior_confirmation_trading_days"]),
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _source_row_with_timing(
    row: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    source_name = str(row.get("source_name") or "").upper()
    signal_date = _date10(row.get("signal_date") or row.get("date") or as_of)
    timed = deepcopy(row)
    timed["source_name"] = source_name
    timed["date"] = signal_date
    timed["signal_date"] = signal_date
    timed["source_family"] = _source_family(source_name, config)
    timed["timing_role"] = "current" if signal_date == as_of else "prior_confirmation"
    timed["confirmation_lag_trading_days"] = None
    return timed


def _lagged_source_rows_for_ticker(
    *,
    ticker: str,
    as_of: str,
    history_signal_dates: list[str],
    history_source_rows_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    date_index = {date_value: idx for idx, date_value in enumerate(history_signal_dates)}
    as_of_idx = date_index.get(as_of)
    for source_date in history_signal_dates:
        lag = (as_of_idx - date_index[source_date]) if as_of_idx is not None else None
        for row in (history_source_rows_by_key.get((source_date, ticker)) or {}).values():
            timed = _source_row_with_timing(row, as_of=as_of, config=config)
            timed["confirmation_lag_trading_days"] = lag
            rows.append(timed)
    return rows


def _trading_dates_from_rows(rows_by_ticker: dict[str, list[dict[str, Any]]], as_of: str) -> list[str]:
    preferred = rows_by_ticker.get("SPY")
    source_rows = preferred if preferred else next(iter(rows_by_ticker.values()), [])
    dates = sorted(
        {
            _date10(row.get("date"))
            for row in source_rows or []
            if isinstance(row, dict) and row.get("date") and _date10(row.get("date")) <= as_of
        }
    )
    return dates


def _prior_confirmation_dates(
    trading_dates: list[str],
    *,
    as_of: str,
    prior_trading_days: int,
) -> list[str]:
    if as_of not in trading_dates:
        return [as_of]
    as_of_idx = trading_dates.index(as_of)
    first_idx = max(0, as_of_idx - max(0, int(prior_trading_days)))
    return trading_dates[first_idx : as_of_idx + 1]


def load_free_data_cross_source_consensus_source_snapshot_history(
    *,
    as_of: str,
    trading_dates: list[str],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cfg = _config(config)
    valid_dates = set(
        _prior_confirmation_dates(
            trading_dates,
            as_of=as_of,
            prior_trading_days=int(cfg["prior_confirmation_trading_days"]),
        )
    )
    if not valid_dates:
        return []
    snapshots: list[dict[str, Any]] = []
    for source_name, artifact_key in SOURCE_SNAPSHOT_HISTORY_ARTIFACTS.items():
        path = data_artifact_path(artifact_key)
        if not path.exists():
            continue
        for snapshot in _iter_snapshot_log(path, valid_dates=valid_dates):
            snapshots.append(snapshot)
            if source_name == "FINRA_IWM_CONFIRMED_PAPER":
                alias = finra_borrow_pressure_source_snapshot_from_finra_iwm_snapshot(snapshot)
                if alias is not None:
                    snapshots.append(alias)
    return snapshots


def _iter_snapshot_log(path: Path, *, valid_dates: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                snapshot_date = _date10(payload.get("asof_date"))
                if snapshot_date not in valid_dates:
                    continue
                rows.append(payload)
    except OSError:
        return []
    return rows


def _lagged_source_consensus_summary(
    candidates: list[dict[str, Any]],
    *,
    current_source_rows_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]],
    history_source_rows_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]],
    history_signal_dates: list[str],
    config: dict[str, Any],
) -> dict[str, Any]:
    lagged_candidates = [
        row for row in candidates or [] if row.get("has_lagged_independent_confirmation")
    ]
    return {
        "rule_version": LAGGED_CONSENSUS_RULE_VERSION,
        "enabled": bool(config.get("source_history_enabled", True)),
        "prior_confirmation_trading_days": int(config["prior_confirmation_trading_days"]),
        "history_signal_dates": list(history_signal_dates),
        "current_source_key_count": len(current_source_rows_by_key),
        "history_source_key_count": len(history_source_rows_by_key),
        "candidate_count": len(candidates or []),
        "lagged_independent_candidate_count": len(lagged_candidates),
        "same_day_or_already_independent_candidate_count": len(candidates or [])
        - len(lagged_candidates),
        "trade_enabled": False,
        "alters_orders": False,
    }


def finra_borrow_pressure_source_snapshot_from_finra_iwm_snapshot(
    snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Expose FINRA borrow-pressure candidates as a distinct consensus source.

    The source-family map collapses this alias with FINRA_IWM_CONFIRMED_PAPER,
    so it cannot create FINRA+FINRA false consensus. It only lets daily reports
    and forward ledgers carry the accepted borrow-pressure evidence with the
    same source name used by the exp-20260603-014 replay lead.
    """

    if not isinstance(snapshot, dict):
        return None
    candidates = []
    for candidate in snapshot.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("finra_borrow_pressure_pass_v1") is not True:
            continue
        row = deepcopy(candidate)
        row["sleeve"] = "FINRA_BORROW_PRESSURE_PAPER"
        row["source_name"] = "FINRA_BORROW_PRESSURE_PAPER"
        row["source_family"] = "finra_short_pressure"
        candidates.append(row)
    return {
        "schema_version": 1,
        "sleeve": "FINRA_BORROW_PRESSURE_PAPER",
        "asof_date": snapshot.get("asof_date"),
        "generated_at": snapshot.get("generated_at"),
        "source_snapshot_rule_version": "finra_borrow_pressure_consensus_source_alias_v1",
        "source_family_rule_version": SOURCE_FAMILY_RULE_VERSION,
        "derived_from_sleeve": snapshot.get("sleeve"),
        "derived_from_rule_version": snapshot.get("rule_version"),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "trade_enabled": False,
        "alters_orders": False,
    }


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
        current_price = current_prices.get(ticker)
        if current_price is None:
            still_open.append(position)
            continue
        observed_days = int(position.get("observed_trading_days") or 0) + 1
        position["observed_trading_days"] = observed_days
        exit_mark = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
        position["last_price"] = current_price
        position["last_price_asof"] = as_of
        position["unrealized_pnl"] = _pnl(
            position.get("entry_price"),
            exit_mark,
            position.get("notional"),
            float(config["round_trip_cost_pct"]),
        )
        if observed_days >= int(config["hold_days"]):
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_mark,
                    "exit_reason": "max_hold_days",
                    "pnl": _pnl(
                        position.get("entry_price"),
                        exit_mark,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        exit_mark,
                        float(config["round_trip_cost_pct"]),
                    ),
                    "trade_enabled": False,
                    "alters_orders": False,
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
                    "alters_orders": False,
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
            "strategy": "accepted_free_data_cross_source_consensus_candidate_pool",
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
            "alters_orders": False,
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


def _source_consensus_summary(
    candidates: list[dict[str, Any]],
    source_rows_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]],
    config: dict[str, Any],
    *,
    history_source_rows_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]] | None = None,
    history_signal_dates: list[str] | None = None,
) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    source_key_counts: dict[str, int] = {}
    source_family_counts: dict[str, int] = {}
    source_family_key_counts: dict[str, int] = {}
    for source_rows in source_rows_by_key.values():
        for source_name in source_rows:
            source_key_counts[source_name] = source_key_counts.get(source_name, 0) + 1
        for family in {_source_family(source_name, config) for source_name in source_rows}:
            source_family_key_counts[family] = source_family_key_counts.get(family, 0) + 1
    for row in candidates:
        for source_name in row.get("source_names") or []:
            source_counts[source_name] = source_counts.get(source_name, 0) + 1
        for family in row.get("source_families") or []:
            source_family_counts[family] = source_family_counts.get(family, 0) + 1
    return {
        "rule_version": CONSENSUS_RULE_VERSION,
        "source_family_rule_version": SOURCE_FAMILY_RULE_VERSION,
        "lagged_consensus_rule_version": LAGGED_CONSENSUS_RULE_VERSION,
        "enabled": True,
        "source_names": list(config.get("accepted_source_names") or []),
        "source_families": dict(sorted((config.get("source_families") or {}).items())),
        "min_source_count": int(config["min_source_count"]),
        "min_source_family_count": int(config["min_source_family_count"]),
        "prior_confirmation_trading_days": int(config["prior_confirmation_trading_days"]),
        "history_signal_dates": list(history_signal_dates or []),
        "source_key_count": len(source_rows_by_key),
        "history_source_key_count": len(history_source_rows_by_key or {}),
        "candidate_count": len(candidates),
        "supported_candidate_count": len(candidates),
        "lagged_independent_supported_candidate_count": sum(
            1 for row in candidates if row.get("has_lagged_independent_confirmation")
        ),
        "source_counts": dict(sorted(source_counts.items())),
        "source_key_counts": dict(sorted(source_key_counts.items())),
        "source_family_counts": dict(sorted(source_family_counts.items())),
        "source_family_key_counts": dict(sorted(source_family_key_counts.items())),
        "paper_notional_usd": float(config["paper_notional_usd"]),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _core_capacity_context(
    *,
    core_active_position_count: int | None,
    max_core_positions: int | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    required = bool(config.get("require_core_capacity_available", True))
    max_positions = int(max_core_positions or config.get("max_core_positions") or MAX_POSITIONS)
    active = _non_negative_int(core_active_position_count)
    available_slots = max(0, max_positions - active) if active is not None else None
    return {
        "rule_version": CORE_CAPACITY_RULE_VERSION,
        "required": required,
        "known": active is not None,
        "active_core_positions_after_signal_close": active,
        "max_core_positions": max_positions,
        "available_core_slots_after_signal_close": available_slots,
        "available": (available_slots is not None and available_slots > 0)
        if required
        else True,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _candidate_capacity_fields(capacity: dict[str, Any]) -> dict[str, Any]:
    return {
        "core_capacity_rule_version": capacity["rule_version"],
        "capacity_gate": "core_capacity_available_after_signal_close",
        "core_capacity_required": capacity["required"],
        "active_core_positions_after_signal_close": capacity[
            "active_core_positions_after_signal_close"
        ],
        "available_core_slots_after_signal_close": capacity[
            "available_core_slots_after_signal_close"
        ],
        "max_core_positions": capacity["max_core_positions"],
    }


def _core_capacity_gate_summary(
    *,
    core_active_position_count: int | None,
    max_core_positions: int | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    capacity = _core_capacity_context(
        core_active_position_count=core_active_position_count,
        max_core_positions=max_core_positions,
        config=config,
    )
    status = "passed" if capacity["available"] else "blocked"
    if capacity["required"] and not capacity["known"]:
        status = "blocked"
        reasons = ["missing_core_capacity_context"]
    elif capacity["required"] and not capacity["available"]:
        reasons = ["core_capacity_full"]
    else:
        reasons = []
    return {
        "rule_version": CORE_CAPACITY_RULE_VERSION,
        "required": capacity["required"],
        "status": status,
        "passed": not reasons,
        "reasons": reasons,
        "metrics": {
            "active_core_positions_after_signal_close": capacity[
                "active_core_positions_after_signal_close"
            ],
            "available_core_slots_after_signal_close": capacity[
                "available_core_slots_after_signal_close"
            ],
            "max_core_positions": capacity["max_core_positions"],
        },
        "trade_enabled": False,
        "alters_orders": False,
    }


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed = [row for row in closed_positions or [] if isinstance(row, dict)]
    realized = round(sum(_money(row.get("pnl")) for row in closed), 2)
    wins = sum(1 for row in closed if _money(row.get("pnl")) > 0)
    win_rate = round(wins / len(closed), 4) if closed else None
    single_share = _single_ticker_positive_share(closed)
    hhi = _positive_pnl_hhi(closed)
    checks = {
        "min_closed_trades": len(closed) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0
        if config.get("forward_gate_positive_net_pnl", True)
        else True,
        "min_win_rate": win_rate is not None
        and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None
        and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_positive_pnl_hhi": hhi is not None
        and hhi <= float(config["forward_gate_max_positive_pnl_hhi"]),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": len(closed),
            "realized_pnl": realized,
            "win_rate": win_rate,
            "single_ticker_positive_share": single_share,
            "positive_pnl_hhi": hhi,
        },
        "trade_enabled_after_gate": False,
    }


def _positive_pnl_hhi(closed_positions: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    for row in closed_positions or []:
        if not isinstance(row, dict):
            continue
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(sum((value / total) ** 2 for value in by_ticker.values()), 6)


def _entry_notional(entry: dict[str, Any], config: dict[str, Any]) -> float:
    notional = _positive_float(entry.get("notional"))
    if notional is not None:
        return notional
    candidate = entry.get("candidate") or {}
    candidate_notional = _positive_float(candidate.get("intended_notional"))
    if candidate_notional is not None:
        return candidate_notional
    return float(config["paper_notional_usd"])


def _non_negative_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, parsed)


def _last_selected_date(state: dict[str, Any], ticker: str) -> str | None:
    dates: list[str] = []
    for bucket in ("pending_entries", "open_positions", "closed_positions", "skipped_entries"):
        for row in state.get(bucket) or []:
            if not isinstance(row, dict) or _row_ticker(row) != ticker:
                continue
            candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
            for key in ("signal_date", "date", "created_asof", "entry_date", "exit_date"):
                value = candidate.get(key) if key in candidate else row.get(key)
                if value:
                    dates.append(_date10(value))
                    break
    return max(dates) if dates else None


def _within_cooldown(as_of: str, last_selected: str | None, cooldown_days: int) -> bool:
    if not last_selected:
        return False
    try:
        current = date.fromisoformat(_date10(as_of))
        prior = date.fromisoformat(_date10(last_selected))
    except ValueError:
        return False
    return 0 <= (current - prior).days <= cooldown_days


def _row_ticker(row: dict[str, Any]) -> str:
    ticker = str(row.get("ticker") or "").upper()
    if not ticker and isinstance(row.get("candidate"), dict):
        ticker = str(row["candidate"].get("ticker") or "").upper()
    return ticker


def _pending_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("created_asof") or ""), str(row.get("ticker") or ""))


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
    cfg["accepted_source_names"] = sorted(
        {str(name).upper() for name in cfg.get("accepted_source_names") or []}
    )
    source_families = dict(SOURCE_FAMILIES)
    source_families.update(
        {
            str(name).upper(): str(family)
            for name, family in (cfg.get("source_families") or {}).items()
            if name and family
        }
    )
    cfg["source_families"] = source_families
    cfg["max_core_positions"] = int(cfg.get("max_core_positions") or MAX_POSITIONS)
    cfg["min_source_family_count"] = int(
        cfg.get("min_source_family_count") or cfg.get("min_source_count") or 2
    )
    cfg["require_core_capacity_available"] = bool(
        cfg.get("require_core_capacity_available", True)
    )
    cfg["source_history_enabled"] = bool(cfg.get("source_history_enabled", True))
    cfg["prior_confirmation_trading_days"] = max(
        0,
        int(cfg.get("prior_confirmation_trading_days") or 0),
    )
    return cfg


def _source_family(source_name: str, config: dict[str, Any]) -> str:
    name = str(source_name).upper()
    return str((config.get("source_families") or {}).get(name) or name)


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "default_off_accepted_free_data_cross_source_consensus_paper_attribution",
    }
