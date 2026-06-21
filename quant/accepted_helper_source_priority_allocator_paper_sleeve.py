"""Default-off accepted-helper source-priority allocator.

Shared helper for the positive exp-20260610-004 replay lead. The helper treats
accepted single-stock default-off paper helpers as competing sources for one
paper risk slot per signal date, using a fixed ex-ante source priority.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import macro_relief_leadership_paper_sleeve as leader
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from industry_relative_laggard_repair_paper_sleeve import (
        build_industry_relative_laggard_repair_historical_trades,
    )
    from industry_stable_core_flow_paper_sleeve import (
        build_industry_stable_core_flow_historical_trades,
    )
    from narrow_range_compression_breakout_paper_sleeve import (
        build_narrow_range_compression_breakout_historical_trades,
    )
    from revision_surprise_low_extension_paper_sleeve import (
        build_revision_surprise_low_extension_historical_trades,
    )
    from rolling_corr_peer_shock_paper_sleeve import (
        build_rolling_corr_peer_shock_historical_trades,
    )
    from turn_of_month_liquid_leadership_paper_sleeve import (
        build_turn_of_month_liquid_leadership_historical_trades,
    )
    from volatility_relief_stock_leadership_paper_sleeve import (
        build_volatility_relief_stock_leadership_historical_trades,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import macro_relief_leadership_paper_sleeve as leader
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.industry_relative_laggard_repair_paper_sleeve import (
        build_industry_relative_laggard_repair_historical_trades,
    )
    from quant.industry_stable_core_flow_paper_sleeve import (
        build_industry_stable_core_flow_historical_trades,
    )
    from quant.narrow_range_compression_breakout_paper_sleeve import (
        build_narrow_range_compression_breakout_historical_trades,
    )
    from quant.revision_surprise_low_extension_paper_sleeve import (
        build_revision_surprise_low_extension_historical_trades,
    )
    from quant.rolling_corr_peer_shock_paper_sleeve import (
        build_rolling_corr_peer_shock_historical_trades,
    )
    from quant.turn_of_month_liquid_leadership_paper_sleeve import (
        build_turn_of_month_liquid_leadership_historical_trades,
    )
    from quant.volatility_relief_stock_leadership_paper_sleeve import (
        build_volatility_relief_stock_leadership_historical_trades,
    )


SLEEVE_NAME = "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER"
RULE_VERSION = "accepted_helper_source_priority_shared_default_off_allocator_v3"
SOURCE_RULE_VERSION = (
    "accepted_helper_source_priority_top1_with_peer_shock_source_notional_v2"
)
STATE_SCHEMA_VERSION = 1
LAGGED_CONSENSUS_SOURCE_ARTIFACT = (
    DATA_ROOT
    / "experiments"
    / "exp-20260604-008"
    / "lagged_independent_source_consensus.json"
)

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "accepted_helper_source_priority_allocator" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT
    / "paper_sleeves"
    / "accepted_helper_source_priority_allocator"
    / "snapshots.jsonl"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 12

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": BASE_NOTIONAL_USD,
    "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
    "max_active_positions": 8,
    "hold_days": HOLD_DAYS,
    "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "source_notional_scalars": {
        "industry_laggard_repair": 1.25,
        "revision_surprise_low_extension": 1.25,
        "rolling_peer_shock": 1.25,
    },
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_positive_hhi": 0.35,
}

SOURCE_NOTIONAL_SCALARS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("industry_laggard_repair", 1.25),
        ("revision_surprise_low_extension", 1.25),
        ("rolling_peer_shock", 1.25),
    ]
)

SOURCE_PRIORITY: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "lagged_cross_source_consensus",
            {
                "rank": 1,
                "description": "accepted lagged cross-source consensus",
                "accepted_experiment": "exp-20260604-009",
                "accepted_ev_delta_sum": 1.9949,
                "accepted_pnl_delta_sum": 35553.87,
            },
        ),
        (
            "volatility_relief",
            {
                "rank": 2,
                "description": "accepted volatility relief stock leadership",
                "accepted_experiment": "exp-20260607-019",
                "accepted_ev_delta_sum": 0.5732,
                "accepted_pnl_delta_sum": 11934.79,
            },
        ),
        (
            "rolling_peer_shock",
            {
                "rank": 3,
                "description": "accepted rolling correlation peer shock",
                "accepted_experiment": "exp-20260606-025",
                "accepted_ev_delta_sum": 0.3845,
                "accepted_pnl_delta_sum": 6107.66,
            },
        ),
        (
            "turn_of_month",
            {
                "rank": 4,
                "description": "accepted turn-of-month liquid leadership",
                "accepted_experiment": "exp-20260609-027",
                "accepted_ev_delta_sum": 0.2774,
                "accepted_pnl_delta_sum": 5287.69,
            },
        ),
        (
            "industry_laggard_repair",
            {
                "rank": 5,
                "description": "accepted industry relative laggard repair",
                "accepted_experiment": "exp-20260607-008",
                "accepted_ev_delta_sum": 0.2763,
                "accepted_pnl_delta_sum": 4875.91,
            },
        ),
        (
            "revision_surprise_low_extension",
            {
                "rank": 6,
                "description": "accepted revision-surprise low-extension expectation source",
                "accepted_experiment": "exp-20260609-011",
                "accepted_ev_delta_sum": 0.1846,
                "accepted_pnl_delta_sum": 2893.75,
            },
        ),
        (
            "compression",
            {
                "rank": 7,
                "description": "accepted narrow range compression breakout",
                "accepted_experiment": "exp-20260608-013",
                "accepted_ev_delta_sum": 0.1608,
                "accepted_pnl_delta_sum": 2248.98,
            },
        ),
        (
            "industry_stable_core_flow",
            {
                "rank": 8,
                "description": "accepted industry stable core-flow",
                "accepted_experiment": "exp-20260608-008",
                "accepted_ev_delta_sum": 0.1459,
                "accepted_pnl_delta_sum": 3523.28,
            },
        ),
    ]
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_accepted_helper_source_priority_allocator_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_accepted_helper_source_priority_allocator_snapshot(
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
        "source_priority_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_accepted_helper_source_priority_allocator_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_accepted_helper_source_priority_allocator_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_accepted_helper_source_priority_allocator_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_accepted_helper_source_priority_allocator_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(leader._safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_accepted_helper_source_priority_allocator_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(leader._safe(snapshot), sort_keys=True) + "\n")


def build_accepted_helper_source_priority_allocator_snapshot(
    *,
    as_of: str,
    source_snapshots: dict[str, dict[str, Any]] | None,
    ohlcv_by_ticker: dict[str, Any],
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = leader._date10(as_of)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    if not rows_by_ticker:
        return empty_accepted_helper_source_priority_allocator_snapshot(
            as_of_date,
            "missing_ohlcv",
        )

    working_state = deepcopy(
        state
        if state is not None
        else load_accepted_helper_source_priority_allocator_state(state_path)
    )
    _normalise_state(working_state)
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
    source_rows, source_coverage = source_rows_from_snapshots(
        source_snapshots or {},
        as_of=as_of_date,
    )
    selected, rejected, priority_audit = select_accepted_helper_source_priority_rows(
        source_rows=source_rows,
        trading_dates=_trading_dates(rows_by_ticker),
        existing_state=working_state,
        config=cfg,
        create_trades=False,
    )
    if len(working_state.get("pending_entries") or []) + len(
        working_state.get("open_positions") or []
    ) >= int(cfg["max_active_positions"]):
        rejected.extend({**row, "filter_reason": "max_active_positions"} for row in selected)
        selected = []

    new_pending_entries: list[dict[str, Any]] = []
    if cfg.get("paper_enabled", True):
        for row in selected:
            pending = _pending_entry_from_candidate(row, cfg)
            if not leader._has_pending_open_or_closed_decision(
                working_state,
                pending["decision_id"],
            ):
                working_state["pending_entries"].append(pending)
                new_pending_entries.append(pending)

    if not selected and not source_rows:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_source_candidates"))
    elif not selected and source_rows:
        _append_skip_once(working_state, _skip_payload(as_of_date, "source_candidates_filtered"))

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        source_rows=source_rows,
        selected_rows=selected,
        rejected=rejected,
        source_coverage=source_coverage,
        priority_audit=priority_audit,
        new_pending_entries=new_pending_entries,
        filled_today=filled_today,
        closed_today=closed_today,
        rows_by_ticker=rows_by_ticker,
        config=cfg,
    )
    if persist:
        save_accepted_helper_source_priority_allocator_state(working_state, state_path)
        append_accepted_helper_source_priority_allocator_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_accepted_helper_source_priority_allocator_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    calendar_dates: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    sector_map = _sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    all_selected: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "source_priority": SOURCE_PRIORITY,
        "source_notional_scalars": _source_notional_scalars(cfg),
        "selected_by_window": {},
        "selected_source_counts_by_window": {},
        "source_trade_counts_by_window": {},
        "raw_candidate_counts_by_window": {},
        "filtered_count_by_window": {},
        "source_audits_by_window": {},
        "priority_audit_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in _trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        source_trades, source_audit = _build_source_trades(
            rows_by_ticker=rows_by_ticker,
            dates=dates,
            window_label=label,
            window=window,
            core_entries_by_date=core_entries_by_date or {},
            sector_entries=sector_map,
            candidate_universe=candidate_universe,
            calendar_dates=calendar_dates,
        )
        selected, filtered, priority_audit = select_accepted_helper_source_priority_rows(
            source_rows=source_trades,
            trading_dates=dates,
            config=cfg,
            create_trades=True,
        )
        window_selected = [{**row, "window": label} for row in selected]
        all_selected.extend(window_selected)
        audit["selected_by_window"][label] = len(window_selected)
        audit["selected_source_counts_by_window"][label] = dict(
            Counter(str(row.get("source_family") or "unknown") for row in window_selected)
        )
        audit["source_trade_counts_by_window"][label] = source_audit["source_trade_counts"]
        audit["raw_candidate_counts_by_window"][label] = source_audit[
            "raw_candidate_counts"
        ]
        audit["filtered_count_by_window"][label] = len(filtered)
        audit["source_audits_by_window"][label] = source_audit["source_audits"]
        audit["priority_audit_by_window"][label] = priority_audit
    audit["total_selected"] = len(all_selected)
    return all_selected, leader._safe(audit)


def source_rows_from_snapshots(
    source_snapshots: dict[str, dict[str, Any]],
    *,
    as_of: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    coverage: dict[str, Any] = {}
    for source_family in SOURCE_PRIORITY:
        snapshot = source_snapshots.get(source_family) or {}
        candidates = list(snapshot.get("candidates") or [])
        if snapshot.get("candidate") and snapshot.get("candidate") not in candidates:
            candidates.append(snapshot["candidate"])
        coverage[source_family] = {
            "present": bool(snapshot),
            "error": snapshot.get("error"),
            "candidate_count": snapshot.get("candidate_count", len(candidates)),
            "raw_candidate_count": snapshot.get("raw_candidate_count"),
            "rule_version": snapshot.get("rule_version"),
            "source_rule_version": snapshot.get("source_rule_version"),
        }
        for row in candidates:
            if not isinstance(row, dict):
                continue
            signal_date = str(row.get("signal_date") or row.get("date") or as_of)[:10]
            if signal_date != as_of:
                continue
            rows.append(_normalise_source_row(row, source_family))
    return rows, coverage


def select_accepted_helper_source_priority_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    create_trades: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    candidates = [
        _normalise_source_row(row, str(row.get("source_family") or ""))
        for row in source_rows
        if str(row.get("source_family") or "") in SOURCE_PRIORITY
    ]
    candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or "")[:10],
            int(row.get("source_priority_rank") or 999),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        )
    )
    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    used_date_counts: Counter[str] = Counter()
    next_allowed_pos_by_ticker = _state_cooldown_map(
        existing_state=existing_state,
        date_position=date_position,
        config=cfg,
    )
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_position.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if used_date_counts[signal_date] >= int(cfg["daily_entry_slots"]):
            rejected.append({**row, "filter_reason": "daily_top1_source_priority_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        notional_scalar = _source_notional_scalar(row, cfg)
        paper_notional = leader._round(float(cfg["paper_notional_usd"]) * notional_scalar, 2)
        out = _scale_historical_pnl(
            deepcopy(row),
            paper_notional=paper_notional,
        )
        out.update(
            {
                "source": SLEEVE_NAME,
                "sleeve": SLEEVE_NAME,
                "rule_version": RULE_VERSION,
                "source_rule_version": SOURCE_RULE_VERSION,
                "decision_id": _decision_id(row),
                "candidate_score": _allocator_score(row),
                "base_paper_notional_usd": float(cfg["paper_notional_usd"]),
                "source_notional_scalar": notional_scalar,
                "paper_notional_usd": paper_notional,
                "notional_usd": paper_notional,
                "paper_status": "closed" if create_trades else "candidate",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
        selected.append(out)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    audit = {
        "source_candidate_count": len(candidates),
        "selected_priority_trade_count": len(selected),
        "filtered_priority_candidate_count": len(rejected),
        "source_candidate_counts": dict(
            Counter(str(row.get("source_family") or "unknown") for row in candidates)
        ),
        "selected_source_counts": dict(
            Counter(str(row.get("source_family") or "unknown") for row in selected)
        ),
        "daily_entry_slots": int(cfg["daily_entry_slots"]),
        "same_ticker_cooldown_days": int(cfg["same_ticker_cooldown_days"]),
        "source_notional_scalars": _source_notional_scalars(cfg),
    }
    return selected, rejected, audit


def _build_source_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    window_label: str,
    window: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    candidate_universe: dict[str, Any] | list[str] | None,
    calendar_dates: list[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_trades: list[dict[str, Any]] = []
    source_trade_counts: OrderedDict[str, int] = OrderedDict()
    raw_candidate_counts: OrderedDict[str, int | None] = OrderedDict()
    source_audits: OrderedDict[str, Any] = OrderedDict()

    lagged_consensus_trades, lagged_consensus_audit = (
        _build_lagged_cross_source_consensus_historical_trades(
            dates=dates,
            window_label=window_label,
        )
    )
    source_trades.extend(lagged_consensus_trades)
    source_trade_counts["lagged_cross_source_consensus"] = len(lagged_consensus_trades)
    raw_candidate_counts["lagged_cross_source_consensus"] = lagged_consensus_audit[
        "raw_candidate_count"
    ]
    source_audits["lagged_cross_source_consensus"] = lagged_consensus_audit

    volatility = build_volatility_relief_stock_leadership_historical_trades(
        ohlcv_by_ticker=rows_by_ticker,
        dates=dates,
        candidate_universe=candidate_universe or sector_entries,
        core_entries_by_date=core_entries_by_date,
    )
    volatility_trades = [
        _normalise_source_row(row, "volatility_relief") for row in volatility["trades"]
    ]
    source_trades.extend(volatility_trades)
    source_trade_counts["volatility_relief"] = len(volatility_trades)
    raw_candidate_counts["volatility_relief"] = len(volatility.get("candidates") or [])
    source_audits["volatility_relief"] = {
        "rule_version": volatility.get("rule_version"),
        "source_rule_version": volatility.get("source_rule_version"),
        "context_scan": volatility.get("context_scan"),
    }

    rolling_trades, rolling_audit = build_rolling_corr_peer_shock_historical_trades(
        ohlcv_by_ticker=rows_by_ticker,
        core_entries_by_date=core_entries_by_date,
        windows=OrderedDict([(window_label, window)]),
        candidate_universe=candidate_universe,
        sector_entries=sector_entries,
    )
    rolling_normalised = [
        _normalise_source_row(row, "rolling_peer_shock") for row in rolling_trades
    ]
    source_trades.extend(rolling_normalised)
    source_trade_counts["rolling_peer_shock"] = len(rolling_normalised)
    raw_candidate_counts["rolling_peer_shock"] = rolling_audit.get(
        "raw_candidate_count_by_window",
        {},
    ).get(window_label)
    source_audits["rolling_peer_shock"] = {
        "rule_version": rolling_audit.get("rule_version"),
        "source_rule_version": rolling_audit.get("source_rule_version"),
        "scan": rolling_audit.get("scan_by_window", {}).get(window_label),
    }

    turn_trades, turn_audit = build_turn_of_month_liquid_leadership_historical_trades(
        ohlcv_by_ticker=rows_by_ticker,
        core_entries_by_date=core_entries_by_date,
        windows=OrderedDict([(window_label, window)]),
        candidate_universe=candidate_universe or sector_entries,
        calendar_dates=calendar_dates or _trading_dates(rows_by_ticker),
    )
    turn_normalised = [_normalise_source_row(row, "turn_of_month") for row in turn_trades]
    source_trades.extend(turn_normalised)
    source_trade_counts["turn_of_month"] = len(turn_normalised)
    raw_candidate_counts["turn_of_month"] = turn_audit.get(
        "raw_candidate_count_by_window",
        {},
    ).get(window_label)
    source_audits["turn_of_month"] = {
        "rule_version": turn_audit.get("rule_version"),
        "source_rule_version": turn_audit.get("source_rule_version"),
        "scan": turn_audit.get("scan_by_window", {}).get(window_label),
    }

    revision_trades, revision_audit = build_revision_surprise_low_extension_historical_trades(
        ohlcv_by_ticker=rows_by_ticker,
        core_entries_by_date=core_entries_by_date,
        windows=OrderedDict([(window_label, window)]),
    )
    revision_normalised = [
        _normalise_source_row(row, "revision_surprise_low_extension")
        for row in revision_trades
    ]
    source_trades.extend(revision_normalised)
    source_trade_counts["revision_surprise_low_extension"] = len(revision_normalised)
    raw_candidate_counts["revision_surprise_low_extension"] = revision_audit.get(
        "raw_candidate_count_by_window",
        {},
    ).get(window_label)
    source_audits["revision_surprise_low_extension"] = {
        "rule_version": revision_audit.get("rule_version"),
        "source_rule_version": revision_audit.get("source_rule_version"),
        "scan": revision_audit.get("scan_by_window", {}).get(window_label),
        "contexts": revision_audit.get("contexts_by_window", {}).get(window_label, [])[:25],
        "source_caveat": (
            "Daily earnings snapshots are replayable, but EPS estimate provenance "
            "remains proxy-grade until vendor PIT provenance and forward rows mature."
        ),
    }

    builders = [
        (
            "industry_laggard_repair",
            build_industry_relative_laggard_repair_historical_trades,
        ),
        ("compression", build_narrow_range_compression_breakout_historical_trades),
        ("industry_stable_core_flow", build_industry_stable_core_flow_historical_trades),
    ]
    for source_family, builder in builders:
        trades, audit = builder(
            ohlcv_by_ticker=rows_by_ticker,
            core_entries_by_date=core_entries_by_date,
            windows=OrderedDict([(window_label, window)]),
            candidate_universe=candidate_universe,
            sector_entries=sector_entries,
        )
        normalised = [_normalise_source_row(row, source_family) for row in trades]
        source_trades.extend(normalised)
        source_trade_counts[source_family] = len(normalised)
        raw_candidate_counts[source_family] = audit.get(
            "raw_candidate_count_by_window",
            {},
        ).get(window_label)
        source_audits[source_family] = {
            "rule_version": audit.get("rule_version"),
            "source_rule_version": audit.get("source_rule_version"),
            "scan": audit.get("scan_by_window", {}).get(window_label),
        }

    return source_trades, {
        "source_priority": SOURCE_PRIORITY,
        "source_trade_counts": dict(source_trade_counts),
        "raw_candidate_counts": dict(raw_candidate_counts),
        "source_audits": dict(source_audits),
    }


def _build_lagged_cross_source_consensus_historical_trades(
    *,
    dates: list[str],
    window_label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    date_set = set(dates)
    payload: dict[str, Any] = {}
    if LAGGED_CONSENSUS_SOURCE_ARTIFACT.exists():
        with LAGGED_CONSENSUS_SOURCE_ARTIFACT.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            payload = loaded

    rows = (payload.get("target_trades_by_window") or {}).get(window_label, [])
    source_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        if signal_date not in date_set or not ticker:
            continue
        source_rows.append(
            _normalise_source_row(
                {
                    **deepcopy(row),
                    "date": signal_date,
                    "signal_date": signal_date,
                    "ticker": ticker,
                    "source_family": "lagged_cross_source_consensus",
                    "source_score": _lagged_consensus_source_score(row),
                    "candidate_score": _lagged_consensus_source_score(row),
                    "source_artifact": str(
                        LAGGED_CONSENSUS_SOURCE_ARTIFACT.relative_to(DATA_ROOT.parent)
                    ).replace("\\", "/"),
                },
                "lagged_cross_source_consensus",
            )
        )

    target_summary = payload.get("target_summary") or {}
    trades_by_window = target_summary.get("trades_by_window") or {}
    return source_rows, {
        "rule_version": "accepted_free_data_cross_source_consensus_shared_v1",
        "source_rule_version": SOURCE_RULE_VERSION,
        "source_artifact": str(
            LAGGED_CONSENSUS_SOURCE_ARTIFACT.relative_to(DATA_ROOT.parent)
        ).replace("\\", "/"),
        "source_trade_count": len(source_rows),
        "raw_candidate_count": trades_by_window.get(window_label, len(source_rows)),
        "unique_source_tickers": len({row["ticker"] for row in source_rows}),
        "selected_source_family_combos": dict(
            Counter("+".join(row.get("source_families") or []) for row in source_rows)
        ),
        "selected_source_name_combos": dict(
            Counter("+".join(row.get("source_names") or []) for row in source_rows)
        ),
        "known_at": (
            "accepted lagged consensus rows from exp-20260604-009 artifact; "
            "daily snapshots use free_data_cross_source_consensus_paper_sleeve"
        ),
        "daily_entry_slots": 1,
    }


def _normalise_source_row(row: dict[str, Any], source_family: str) -> dict[str, Any]:
    if source_family not in SOURCE_PRIORITY:
        source_family = str(row.get("source_family") or "")
    source_meta = SOURCE_PRIORITY[source_family]
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    score = _source_score(row)
    uses_free_non_ohlcv = source_family in {
        "lagged_cross_source_consensus",
        "revision_surprise_low_extension",
    }
    return {
        **deepcopy(row),
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source_family": source_family,
        "source_priority_rank": source_meta["rank"],
        "source_priority_accepted_experiment": source_meta["accepted_experiment"],
        "source_priority_score": leader._round(score, 6),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "uses_llm": False,
        "uses_free_ohlcv_only": not uses_free_non_ohlcv,
        "uses_free_non_ohlcv": uses_free_non_ohlcv,
    }


def _snapshot_payload(
    state: dict[str, Any],
    *,
    as_of: str,
    source_rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    source_coverage: dict[str, Any],
    priority_audit: dict[str, Any],
    new_pending_entries: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
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
        "raw_candidate_count": len(source_rows),
        "rejected_candidate_count": len(rejected),
        "candidate": selected_rows[0] if selected_rows else None,
        "candidates": selected_rows,
        "rejected_candidates": rejected[:50],
        "source_priority_context": {
            "read_only": True,
            "trade_enabled": False,
            "source_priority": SOURCE_PRIORITY,
            "source_coverage": source_coverage,
            "priority_audit": priority_audit,
        },
        "context_scan": priority_audit,
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
        "closed_count_today": len(closed_today),
        "closed_positions": closed,
        "closed_position_count": len(closed),
        "realized_pnl_to_date": leader._round(
            sum(leader._float_or_none(row.get("pnl")) or 0.0 for row in closed),
            2,
        ),
        "unrealized_pnl": leader._unrealized_pnl(open_positions, rows_by_ticker, as_of),
        "forward_paper_gate": leader._forward_paper_gate(closed, config),
        "execution_envelope": EXECUTION_ENVELOPE,
        "kill_switch_state": evaluate_kill_switch_state(closed),
        "parameters": _parameter_summary(config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _pending_entry_from_candidate(candidate: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(candidate)
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
    out.update(
        {
            "decision_id": _decision_id(candidate),
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "base_paper_notional_usd": float(config["paper_notional_usd"]),
            "source_notional_scalar": _source_notional_scalar(candidate, config),
            "paper_notional_usd": float(
                candidate.get("paper_notional_usd")
                or float(config["paper_notional_usd"])
                * _source_notional_scalar(candidate, config)
            ),
            "notional_usd": float(
                candidate.get("notional_usd")
                or candidate.get("paper_notional_usd")
                or float(config["paper_notional_usd"])
                * _source_notional_scalar(candidate, config)
            ),
            "entry_timing": "next_session_open",
            "hold_days": int(config["hold_days"]),
            "paper_status": "pending_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return out


def _state_cooldown_map(
    *,
    existing_state: dict[str, Any] | None,
    date_position: dict[str, int],
    config: dict[str, Any],
) -> dict[str, int]:
    next_allowed_pos_by_ticker: dict[str, int] = {}
    if not existing_state:
        return next_allowed_pos_by_ticker
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_days"):
        for row in existing_state.get(key) or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            pos = date_position.get(signal_date)
            if ticker and pos is not None:
                next_allowed_pos_by_ticker[ticker] = max(
                    next_allowed_pos_by_ticker.get(ticker, -1),
                    pos + int(config["same_ticker_cooldown_days"]),
                )
    return next_allowed_pos_by_ticker


def _sector_entries(
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
        raw_entries = {}
    if isinstance(candidate_universe, list):
        allowed = {str(ticker).upper() for ticker in candidate_universe}
    elif isinstance(candidate_universe, dict) and candidate_universe.get("tickers"):
        allowed = {str(ticker).upper() for ticker in candidate_universe.get("tickers") or []}
    else:
        allowed = set(rows_by_ticker)
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in raw_entries.items():
        ticker_u = str(ticker).upper()
        if ticker_u not in rows_by_ticker or ticker_u not in allowed or not isinstance(meta, dict):
            continue
        sector = meta.get("sector") or meta.get("gics_sector")
        status = meta.get("status") or meta.get("sector_coverage_status") or "ok"
        if not sector or status != "ok":
            continue
        out[ticker_u] = {
            "sector": sector,
            "industry": meta.get("industry"),
            "sector_coverage_status": "ok",
        }
    if out:
        return out
    return {
        ticker: meta
        for ticker, meta in leader._candidate_universe_records(None, rows_by_ticker).items()
        if ticker in rows_by_ticker and ticker in allowed
    }


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_days"):
        if not isinstance(state.get(key), list):
            state[key] = []


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
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    source_family = str(row.get("source_family") or "unknown")
    return f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}:{source_family}"


def _allocator_score(row: dict[str, Any]) -> float:
    rank = max(1, int(row.get("source_priority_rank") or 999))
    return leader._round(1000.0 / rank + _float(row.get("source_priority_score")), 6) or 0.0


def _source_score(row: dict[str, Any]) -> float:
    for key in (
        "candidate_score",
        "paper_candidate_score",
        "peer_shock_score",
        "compression_score",
        "source_score",
        "score",
        "rank_score",
    ):
        if row.get(key) is not None:
            return _float(row.get(key))
    if row.get("source_family_count") is not None or row.get("source_count") is not None:
        return _lagged_consensus_source_score(row)
    return 0.0


def _lagged_consensus_source_score(row: dict[str, Any]) -> float:
    family_count = int(_float(row.get("source_family_count")))
    source_count = int(_float(row.get("source_count")))
    prior_families = int(_float(row.get("prior_confirmation_family_count")))
    lagged = 1.0 if row.get("has_lagged_independent_confirmation") else 0.0
    return family_count * 100.0 + source_count * 10.0 + prior_families + lagged


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})


def _parameter_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_notional_usd": config["paper_notional_usd"],
        "source_notional_scalars": _source_notional_scalars(config),
        "daily_entry_slots": config["daily_entry_slots"],
        "hold_days": config["hold_days"],
        "same_ticker_cooldown_days": config["same_ticker_cooldown_days"],
        "source_priority": SOURCE_PRIORITY,
    }


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _source_notional_scalars(config: dict[str, Any] | None = None) -> dict[str, float]:
    raw = (config or {}).get("source_notional_scalars")
    if not isinstance(raw, dict):
        raw = SOURCE_NOTIONAL_SCALARS
    out: dict[str, float] = {}
    for source_family, scalar in raw.items():
        value = _float(scalar, 1.0)
        if value > 0.0 and value != 1.0:
            out[str(source_family)] = value
    return out


def _source_notional_scalar(row: dict[str, Any], config: dict[str, Any]) -> float:
    source_family = str(row.get("source_family") or "")
    return _source_notional_scalars(config).get(source_family, 1.0)


def _scale_historical_pnl(row: dict[str, Any], *, paper_notional: float | None) -> dict[str, Any]:
    if paper_notional is None or row.get("pnl") is None:
        return row
    pnl_pct = row.get("pnl_pct_net")
    if pnl_pct is not None:
        row["pnl"] = leader._round(float(paper_notional) * _float(pnl_pct), 2)
        return row
    source_notional = _float(row.get("paper_notional_usd") or row.get("notional_usd"))
    if source_notional > 0.0:
        row["pnl"] = leader._round(
            _float(row.get("pnl")) * float(paper_notional) / source_notional,
            2,
        )
    return row


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "default-off paper allocator helper only; core trading policy unchanged",
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
        "uses_free_ohlcv_only": False,
        "uses_free_non_ohlcv": True,
        "adapter_status": "shared_default_off_paper_helper",
        "scope": "accepted_helper_source_priority_allocator_paper_attribution",
    }


# --- Execution envelope (exp-20260612-022) -------------------------------
# Declared dedicated-bucket live-realistic envelope for this sleeve. The
# daily path already caps open positions via max_active_positions; replay
# never enforced it. apply_execution_envelope_to_trades() lets replay measure
# the same constraint plus the kill switch without changing the accepted
# unconstrained replay semantics. trade_enabled stays False.

EXECUTION_ENVELOPE: dict[str, Any] = {
    "rule_version": "accepted_helper_source_priority_allocator_execution_envelope_v2",
    "mode": "dedicated_bucket_zero_core_displacement",
    "bucket_notional_usd": 40_000.0,
    "base_notional_usd": BASE_NOTIONAL_USD,
    "max_source_notional_scalar": 1.25,
    "max_position_notional_usd": 5_000.0,
    "max_concurrent_positions": 8,
    "max_capital_pct_of_bucket": 1.0,
    "min_avg_dollar_volume_20d": 10_000_000.0,
    "max_notional_pct_of_adv20": 0.001,
    "order_semantics": "next_trading_day_open_market_order",
    "missed_fill_policy": "skip_no_chase",
    "halt_policy": "halt_remaining_window_once_triggered",
    "kill_switch_basis": "realized_drawdown_vs_realized_equity_peak",
    "kill_switch_drawdown_pct": 0.15,
    "kill_switch_calibration_note": (
        "15pct is about 1.5x the worst healthy-window giveback (about 10pct of "
        "peak equity in late_strong); calibrated on frozen windows, so the "
        "in-sample no-false-trigger check is partially circular and the binding "
        "validation is OOS plus genuine forward rows (exp-20260612-024)"
    ),
    "core_displacement": 0,
    "slippage_model": (
        "entry/exit 5bps plus ROUND_TRIP_COST_PCT per quant/fill_model.py and "
        "quant/constants.py; conservative for 4k USD orders above the ADV floor"
    ),
    "cash_management_note": (
        "idle bucket cash may sit in the accepted low-deployment ETF substitute "
        "at operator level; not part of sleeve trade policy"
    ),
    "trade_enabled": False,
}


def evaluate_kill_switch_state(
    closed_trades: list[dict[str, Any]] | None,
    *,
    envelope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = {**EXECUTION_ENVELOPE, **(envelope or {})}
    bucket = _float(env["bucket_notional_usd"])
    threshold = _float(env["kill_switch_drawdown_pct"])
    rows = sorted(
        [
            row
            for row in closed_trades or []
            if isinstance(row, dict) and row.get("exit_date")
        ],
        key=lambda row: str(row.get("exit_date") or "")[:10],
    )
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    triggered = False
    trigger_exit_date = None
    for row in rows:
        cumulative += _float(row.get("pnl"))
        peak = max(peak, cumulative)
        equity_peak = bucket + peak
        drawdown = (peak - cumulative) / equity_peak if equity_peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        if not triggered and drawdown >= threshold:
            triggered = True
            trigger_exit_date = str(row.get("exit_date") or "")[:10]
    return {
        "rule_version": env["rule_version"],
        "bucket_notional_usd": bucket,
        "kill_switch_drawdown_pct": threshold,
        "closed_trade_count": len(rows),
        "realized_pnl_usd": leader._round(cumulative, 2),
        "max_realized_drawdown_pct_of_peak_equity": leader._round(max_drawdown, 6),
        "triggered": triggered,
        "trigger_exit_date": trigger_exit_date,
    }


def apply_execution_envelope_to_trades(
    trades: list[dict[str, Any]] | None,
    *,
    envelope: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Enforce the declared execution envelope on a replay trade stream.

    Returns (kept, skipped, audit). Concurrency counts positions whose
    [entry_date, exit_date] span covers the new entry date (exit-day close
    still occupies a slot at the next open). Kill switch halts all further
    entries for the remainder of the stream once realized drawdown crosses
    the threshold. Read-only: input rows are not mutated.
    """
    env = {**EXECUTION_ENVELOPE, **(envelope or {})}
    max_open = int(env["max_concurrent_positions"])
    min_adv = _float(env["min_avg_dollar_volume_20d"])
    ordered = sorted(
        [row for row in trades or [] if isinstance(row, dict)],
        key=lambda row: (str(row.get("entry_date") or "")[:10], str(row.get("ticker") or "")),
    )
    kept: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    halted = False
    halt_entry_date = None
    for row in ordered:
        entry_date = str(row.get("entry_date") or "")[:10]
        exit_date = str(row.get("exit_date") or "")[:10]
        if not entry_date or not exit_date:
            skipped.append({**row, "envelope_skip_reason": "missing_entry_or_exit_date"})
            continue
        if halted:
            skipped.append({**row, "envelope_skip_reason": "kill_switch_halt"})
            continue
        adv_raw = row.get("candidate_avg_dollar_volume_20d")
        if adv_raw is not None and 0.0 <= _float(adv_raw, default=-1.0) < min_adv:
            skipped.append({**row, "envelope_skip_reason": "below_min_adv_floor"})
            continue
        realized_before = [
            kept_row
            for kept_row in kept
            if str(kept_row.get("exit_date") or "")[:10] < entry_date
        ]
        kill_state = evaluate_kill_switch_state(realized_before, envelope=env)
        if kill_state["triggered"]:
            halted = True
            halt_entry_date = entry_date
            skipped.append({**row, "envelope_skip_reason": "kill_switch_halt"})
            continue
        open_count = sum(
            1
            for kept_row in kept
            if str(kept_row.get("entry_date") or "")[:10] <= entry_date
            and str(kept_row.get("exit_date") or "")[:10] >= entry_date
        )
        if open_count >= max_open:
            skipped.append({**row, "envelope_skip_reason": "max_concurrent_positions"})
            continue
        kept.append(row)
    audit = {
        "rule_version": env["rule_version"],
        "max_concurrent_positions": max_open,
        "min_avg_dollar_volume_20d": min_adv,
        "input_trade_count": len(ordered),
        "kept_trade_count": len(kept),
        "skipped_trade_count": len(skipped),
        "skip_reasons": dict(Counter(str(row.get("envelope_skip_reason")) for row in skipped)),
        "kill_switch_halted": halted,
        "kill_switch_halt_entry_date": halt_entry_date,
        "final_kill_switch_state": evaluate_kill_switch_state(kept, envelope=env),
    }
    return kept, skipped, audit
