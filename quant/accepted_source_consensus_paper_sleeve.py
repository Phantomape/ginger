"""Default-off accepted-source consensus paper sleeve.

This adapter promotes the positive exp-20260531-026 replay lead into a shared
production-visible observation boundary. It keeps the accepted alpha-score
market-regime source fixed and admits only rows whose signal-date ticker also
appears in an accepted FINRA/IWM or VBB paper source. It never emits live
orders or changes core signal generation, ranking, sizing, exits, heat, LLM,
or news behavior.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from alpha_score_market_regime_paper_sleeve import (
        DEFAULT_CONFIG as ALPHA_SCORE_DEFAULT_CONFIG,
        MARKET_REGIME_RULE_VERSION,
        SAFE_NOTIONAL_RULE_VERSION,
        SOURCE_RULE_VERSION,
        build_alpha_score_market_regime_candidates,
        build_alpha_score_market_regime_context,
        build_alpha_score_source_consensus_map,
        _date10,
        _exact_asof_price_maps,
        _money,
        _normalise_candidate_universe,
        _normalise_ohlcv_rows,
        _pnl,
        _positive_float,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import data_artifact_path
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.alpha_score_market_regime_paper_sleeve import (
        DEFAULT_CONFIG as ALPHA_SCORE_DEFAULT_CONFIG,
        MARKET_REGIME_RULE_VERSION,
        SAFE_NOTIONAL_RULE_VERSION,
        SOURCE_RULE_VERSION,
        build_alpha_score_market_regime_candidates,
        build_alpha_score_market_regime_context,
        build_alpha_score_source_consensus_map,
        _date10,
        _exact_asof_price_maps,
        _money,
        _normalise_candidate_universe,
        _normalise_ohlcv_rows,
        _pnl,
        _positive_float,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage


SLEEVE_NAME = "ACCEPTED_SOURCE_CONSENSUS_PAPER"
RULE_VERSION = "accepted_source_consensus_shared_v1"
CONSENSUS_RULE_VERSION = "accepted_source_consensus_candidate_pool_v1"
REPLACEMENT_VALUE_RULE_VERSION = "accepted_source_consensus_forward_replacement_value_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("accepted_source_consensus_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path(
    "accepted_source_consensus_paper_snapshots"
)

DEFAULT_CONFIG = {
    **ALPHA_SCORE_DEFAULT_CONFIG,
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "baseline_paper_notional_usd": 10_000.0,
    "source_consensus_enabled": False,
    "source_consensus_notional_scalar": 1.0,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_top5_positive_share": 0.70,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_accepted_source_consensus_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_accepted_source_consensus_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_accepted_source_consensus_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_accepted_source_consensus_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_accepted_source_consensus_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_accepted_source_consensus_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_accepted_source_consensus_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "consensus_rule_version": CONSENSUS_RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "market_regime_rule_version": MARKET_REGIME_RULE_VERSION,
        "safe_notional_rule_version": SAFE_NOTIONAL_RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "rejected_candidate_count": 0,
        "raw_alpha_score_candidate_count": 0,
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
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_accepted_source_consensus_paper_sleeve_snapshot(
    *,
    as_of: str,
    features_by_ticker: dict[str, Any] | None = None,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    source_consensus_snapshots: list[dict[str, Any]] | None = None,
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
    if not features_by_ticker:
        return empty_accepted_source_consensus_paper_sleeve_snapshot(
            as_of_date,
            "missing_features",
        )
    if not rows_by_ticker:
        return empty_accepted_source_consensus_paper_sleeve_snapshot(
            as_of_date,
            "missing_ohlcv",
        )

    working_state = deepcopy(
        state if state is not None else load_accepted_source_consensus_paper_state(state_path)
    )
    _normalise_state(working_state)

    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
    market = build_alpha_score_market_regime_context(
        rows_by_ticker,
        as_of=as_of_date,
        config=cfg,
    )
    if market.get("has_exact_benchmark_price"):
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
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    source_consensus = build_alpha_score_source_consensus_map(
        source_consensus_snapshots,
        as_of=as_of_date,
    )
    raw_candidates, raw_rejected, ranking = build_alpha_score_market_regime_candidates(
        as_of=as_of_date,
        features_by_ticker=features_by_ticker,
        ohlcv_by_ticker=rows_by_ticker,
        candidate_universe=universe,
        market_regime_context=market,
        open_position_tickers=active_tickers,
        pending_tickers=pending_tickers,
        source_consensus_by_key=source_consensus,
        config=cfg,
    )

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = list(raw_rejected)
    for candidate in raw_candidates:
        sources = list(candidate.get("source_consensus_sources") or [])
        if not sources:
            rejected.append({**candidate, "reasons": ["missing_accepted_source_consensus"]})
            continue
        candidates.append(_accepted_source_consensus_candidate(candidate, sources, cfg))

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
    source_summary = _source_consensus_summary(candidates, source_consensus, cfg)
    replacement_value_report = build_accepted_source_consensus_replacement_value_report(
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
        "source_rule_version": SOURCE_RULE_VERSION,
        "market_regime_rule_version": MARKET_REGIME_RULE_VERSION,
        "safe_notional_rule_version": SAFE_NOTIONAL_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_activation_review",
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "raw_alpha_score_candidate_count": len(raw_candidates),
        "source_consensus_key_count": len(source_consensus),
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
        "market_regime_context": market,
        "candidate_universe": {
            "status": universe["status"],
            "ticker_count": len(universe["tickers"]),
        },
        "ranking_surface": ranking,
        "source_consensus": source_summary,
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
        save_accepted_source_consensus_paper_state(working_state, state_path)
        append_accepted_source_consensus_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_accepted_source_consensus_replacement_value_report(
    *,
    candidates: list[dict[str, Any]],
    pending_entries: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    closed_positions: list[dict[str, Any]],
    skipped_entries: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    pending = [row for row in pending_entries or [] if isinstance(row, dict)]
    open_rows = [row for row in open_positions or [] if isinstance(row, dict)]
    closed = [row for row in closed_positions or [] if isinstance(row, dict)]
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
            ticker = str(row.get("ticker") or "").upper()
            if not ticker and isinstance(row.get("candidate"), dict):
                ticker = str(row["candidate"].get("ticker") or "").upper()
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
        "top_ticker_positive_pnl_share": (
            max(
                (
                    float(row.get("positive_pnl_share") or 0.0)
                    for row in by_ticker.values()
                ),
                default=0.0,
            )
            if positive_pnl > 0
            else None
        ),
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


def _accepted_source_consensus_candidate(
    candidate: dict[str, Any],
    sources: list[str],
    config: dict[str, Any],
) -> dict[str, Any]:
    notional = float(config["paper_notional_usd"])
    baseline = float(config["baseline_paper_notional_usd"])
    return {
        **candidate,
        "strategy": "accepted_source_consensus_candidate_pool",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "consensus_rule_version": CONSENSUS_RULE_VERSION,
        "candidate_pool_rule_version": CONSENSUS_RULE_VERSION,
        "accepted_source_consensus_candidate_pool": True,
        "accepted_source_consensus_sources": sorted(sources),
        "accepted_source_consensus_source_count": 1 + len(sources),
        "primary_source": "ALPHA_SCORE_MARKET_REGIME_PAPER",
        "source_consensus_support_applied": False,
        "source_consensus_notional_scalar": 1.0,
        "paper_notional_usd": notional,
        "intended_notional": notional,
        "safe_paper_notional_usd": notional,
        "baseline_safe_paper_notional_usd": notional,
        "safe_notional_scalar": _round(
            notional / baseline if baseline else None,
            6,
        ),
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
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
        exit_reason = "max_hold_days" if observed_days >= int(config["hold_days"]) else None
        if exit_reason:
            exit_price = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
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
            "strategy": "accepted_source_consensus_candidate_pool",
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
    source_consensus_by_key: dict[tuple[str, str], set[str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    for row in candidates:
        for source_name in row.get("accepted_source_consensus_sources") or []:
            source_counts[source_name] = source_counts.get(source_name, 0) + 1
    return {
        "rule_version": CONSENSUS_RULE_VERSION,
        "enabled": True,
        "source_names": list(config.get("source_consensus_sources") or []),
        "source_key_count": len(source_consensus_by_key),
        "candidate_count": len(candidates),
        "supported_candidate_count": len(candidates),
        "source_counts": dict(sorted(source_counts.items())),
        "paper_notional_usd": float(config["paper_notional_usd"]),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    realized = round(sum(_money(row.get("pnl")) for row in closed_positions), 2)
    wins = sum(1 for row in closed_positions if _money(row.get("pnl")) > 0)
    win_rate = round(wins / len(closed_positions), 4) if closed_positions else None
    single_share = _single_ticker_positive_share(closed_positions)
    top5_share = _top5_positive_share(closed_positions)
    checks = {
        "min_closed_trades": len(closed_positions) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0
        if config.get("forward_gate_positive_net_pnl", True)
        else True,
        "min_win_rate": win_rate is not None
        and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None
        and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_top5_positive_share": top5_share is not None
        and top5_share <= float(config["forward_gate_max_top5_positive_share"]),
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
            "top5_positive_share": top5_share,
        },
        "trade_enabled_after_gate": False,
    }


def _entry_notional(entry: dict[str, Any], config: dict[str, Any]) -> float:
    notional = _positive_float(entry.get("notional"))
    if notional is not None:
        return notional
    candidate = entry.get("candidate") or {}
    candidate_notional = _positive_float(candidate.get("intended_notional"))
    if candidate_notional is not None:
        return candidate_notional
    return float(config["paper_notional_usd"])


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
    cfg["source_consensus_enabled"] = False
    cfg["source_consensus_notional_scalar"] = 1.0
    return cfg


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
        "scope": "default_off_accepted_source_consensus_paper_attribution",
    }
