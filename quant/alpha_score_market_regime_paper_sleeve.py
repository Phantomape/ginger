"""Default-off alpha-score market-regime paper sleeve.

This adapter promotes the accepted exp-20260531-021 replay lead into a shared
production-visible observation boundary. It keeps the alpha-score source,
market gate, hold, and $4,000 base paper notional fixed. The accepted
exp-20260531-024 source-consensus support is metadata plus paper-notional
only. It emits only paper candidates and ledger state; it never emits live
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
    from constants import ROUND_TRIP_COST_PCT
    from cross_sectional_ranking_surface import build_cross_sectional_ranking_surface
    from data_paths import data_artifact_path
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from risk_engine import SECTOR_MAP
    from volume_breadth_breakout_paper_sleeve import (
        _close_location_value,
        _close_return,
        _date10,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _normalise_prices,
        _pnl,
        _positive_float,
        _prior_average,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.cross_sectional_ranking_surface import build_cross_sectional_ranking_surface
    from quant.data_paths import data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.risk_engine import SECTOR_MAP
    from quant.volume_breadth_breakout_paper_sleeve import (
        _close_location_value,
        _close_return,
        _date10,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_ohlcv_rows,
        _normalise_prices,
        _pnl,
        _positive_float,
        _prior_average,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )


SLEEVE_NAME = "ALPHA_SCORE_MARKET_REGIME_PAPER"
RULE_VERSION = "alpha_score_market_regime_safe_notional_shared_v1"
SOURCE_RULE_VERSION = "full_universe_alpha_score_top1_20d_v1"
MARKET_REGIME_RULE_VERSION = "alpha_score_market_regime_risk_appetite_v1"
SAFE_NOTIONAL_RULE_VERSION = "full_universe_alpha_score_market_regime_safe_notional_0p40_v1"
SOURCE_CONSENSUS_RULE_VERSION = "alpha_score_market_regime_source_consensus_support_1p25_v1"
REPLACEMENT_VALUE_RULE_VERSION = "alpha_score_market_regime_forward_replacement_value_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("alpha_score_market_regime_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path(
    "alpha_score_market_regime_paper_snapshots"
)

EXCLUDED_TICKERS = {
    "ARKX",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SNXX",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 4_000.0,
    "baseline_paper_notional_usd": 10_000.0,
    "alpha_score_top_decile_threshold": 0.10,
    "daily_entry_slots": 1,
    "max_active_positions": 5,
    "hold_days": 20,
    "avg_dollar_volume_days": 20,
    "min_avg_dollar_volume_20d": 40_000_000.0,
    "spy_ma_days": 50,
    "market_ret_days": 20,
    "min_iwm_minus_spy_ret20": 0.0,
    "source_consensus_enabled": True,
    "source_consensus_notional_scalar": 1.25,
    "source_consensus_sources": [
        "FINRA_IWM_CONFIRMED_PAPER",
        "VOLUME_BREADTH_BREAKOUT_PAPER",
    ],
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 20,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_top5_positive_share": 0.70,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_alpha_score_market_regime_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_alpha_score_market_regime_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_alpha_score_market_regime_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_alpha_score_market_regime_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_alpha_score_market_regime_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_alpha_score_market_regime_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_alpha_score_market_regime_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "market_regime_rule_version": MARKET_REGIME_RULE_VERSION,
        "safe_notional_rule_version": SAFE_NOTIONAL_RULE_VERSION,
        "source_consensus_rule_version": SOURCE_CONSENSUS_RULE_VERSION,
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
        "market_regime_context": {"passed": False, "status": reason},
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "ranking_surface": {"status": reason, "ranked_count": 0},
        "source_consensus_support": {
            "rule_version": SOURCE_CONSENSUS_RULE_VERSION,
            "enabled": False,
            "supported_candidate_count": 0,
            "source_counts": {},
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_alpha_score_market_regime_paper_sleeve_snapshot(
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
        return empty_alpha_score_market_regime_paper_sleeve_snapshot(
            as_of_date,
            "missing_features",
        )
    if not rows_by_ticker:
        return empty_alpha_score_market_regime_paper_sleeve_snapshot(
            as_of_date,
            "missing_ohlcv",
        )

    working_state = deepcopy(
        state
        if state is not None
        else load_alpha_score_market_regime_paper_state(state_path)
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
    candidates, rejected, ranking = build_alpha_score_market_regime_candidates(
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

    open_positions = working_state.get("open_positions") or []
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))
    # Same-signal-day idempotency guard: a re-run for an as_of that a prior run
    # already processed must not grant a fresh daily slot. Count pending entries
    # already created for this as_of and subtract them from daily_entry_slots so
    # re-running the sleeve for one close date is idempotent (state.json pending
    # stays capped at daily_entry_slots per signal day instead of accumulating).
    pending_for_asof = sum(
        1
        for row in working_state.get("pending_entries") or []
        if isinstance(row, dict) and _date10(row.get("created_asof")) == as_of_date
    )
    new_pending = []
    if room > 0 and cfg.get("paper_enabled", True):
        daily_room = max(0, int(cfg["daily_entry_slots"]) - pending_for_asof)
        capacity = min(room, daily_room)
        for candidate in candidates[:capacity]:
            entry = _pending_entry_from_candidate(candidate, as_of=as_of_date, config=cfg)
            working_state["pending_entries"].append(entry)
            new_pending.append(entry)
    for candidate in candidates[len(new_pending):]:
        rejected.append({**candidate, "reasons": ["daily_top1_or_capacity_limit"]})

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    replacement_value_report = build_alpha_score_market_regime_replacement_value_report(
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
        "market_regime_rule_version": MARKET_REGIME_RULE_VERSION,
        "safe_notional_rule_version": SAFE_NOTIONAL_RULE_VERSION,
        "source_consensus_rule_version": SOURCE_CONSENSUS_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_activation_review",
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "raw_candidate_count": ranking.get("top_decile_count", 0),
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
        "source_consensus_support": _source_consensus_support_summary(
            candidates,
            source_consensus,
            cfg,
        ),
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
        save_alpha_score_market_regime_paper_state(working_state, state_path)
        append_alpha_score_market_regime_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_alpha_score_market_regime_candidates(
    *,
    as_of: str,
    features_by_ticker: dict[str, Any],
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    market_regime_context: dict[str, Any] | None = None,
    open_position_tickers: set[str] | None = None,
    pending_tickers: set[str] | None = None,
    source_consensus_by_key: dict[tuple[str, str], set[str]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    universe_tickers = set(universe["tickers"])
    active = {str(value).upper() for value in (open_position_tickers or set())}
    pending = {str(value).upper() for value in (pending_tickers or set())}
    surface = build_cross_sectional_ranking_surface(features_by_ticker or {})
    ranked_rows = [
        row
        for row in surface.get("rows") or []
        if str(row.get("ticker") or "").upper() in universe_tickers
        and str(row.get("ticker") or "").upper() not in EXCLUDED_TICKERS
    ]
    ranked_count = len(ranked_rows)
    threshold = float(cfg["alpha_score_top_decile_threshold"])
    market = market_regime_context or build_alpha_score_market_regime_context(
        rows_by_ticker,
        as_of=as_of_date,
        config=cfg,
    )

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    top_decile_count = 0

    for rank, ranked in enumerate(ranked_rows, start=1):
        ticker = str(ranked.get("ticker") or "").upper()
        rank_pct = rank / ranked_count if ranked_count else None
        if rank_pct is None or rank_pct > threshold:
            continue
        top_decile_count += 1
        candidate = _candidate_from_ranked_row(
            ranked,
            ticker=ticker,
            rank=rank,
            rank_pct=rank_pct,
            rows_by_ticker=rows_by_ticker,
            as_of=as_of_date,
            config=cfg,
        )
        if candidate is None:
            rejected.append(
                {
                    "date": as_of_date,
                    "signal_date": as_of_date,
                    "ticker": ticker,
                    "alpha_score": _round(ranked.get("alpha_score"), 6),
                    "alpha_score_rank": rank,
                    "alpha_score_rank_pct": _round(rank_pct, 6),
                    "alpha_score_bucket": _rank_bucket(rank_pct),
                    "trade_enabled": False,
                    "alters_orders": False,
                    "reasons": ["missing_signal_date_price_or_liquidity"],
                }
            )
            continue
        _apply_source_consensus_support(
            candidate,
            source_consensus_by_key or {},
            cfg,
        )
        reasons = []
        if market.get("passed") is not True:
            reasons.append("market_regime_gate_failed")
        if ticker in active:
            reasons.append("already_open_in_paper_sleeve")
        if ticker in pending:
            reasons.append("already_pending_in_paper_sleeve")
        candidate["market_regime_context"] = deepcopy(market)
        if reasons:
            rejected.append({**candidate, "reasons": reasons})
            continue
        accepted.append(candidate)

    accepted.sort(
        key=lambda row: (
            -float(row["alpha_score"]),
            float(row["alpha_score_rank_pct"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    for rank, candidate in enumerate(accepted, start=1):
        candidate["alpha_score_market_regime_candidate_rank_on_signal_date"] = rank
        candidate["max_paper_trades_per_day"] = int(cfg["daily_entry_slots"])

    ranking = _ranking_surface_summary(
        surface=surface,
        ranked_rows=ranked_rows,
        threshold=threshold,
        top_decile_count=top_decile_count,
    )
    return accepted, rejected, ranking


def build_alpha_score_source_consensus_map(
    snapshots: list[dict[str, Any]] | None,
    *,
    as_of: str,
) -> dict[tuple[str, str], set[str]]:
    as_of_date = _date10(as_of)
    keys: dict[tuple[str, str], set[str]] = {}
    for snapshot in snapshots or []:
        if not isinstance(snapshot, dict):
            continue
        source_name = str(snapshot.get("sleeve") or snapshot.get("name") or "").upper()
        if source_name not in set(DEFAULT_CONFIG["source_consensus_sources"]):
            continue
        for row in _source_consensus_candidate_rows(snapshot):
            key = _source_consensus_key(row)
            if key is None or key[0] != as_of_date:
                continue
            keys.setdefault(key, set()).add(source_name)
    return keys


def _source_consensus_candidate_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in snapshot.get("candidates") or []:
        if isinstance(row, dict):
            rows.append(row)
    for entry_key in ("new_pending_entries", "filled_entries"):
        for row in snapshot.get(entry_key) or []:
            if not isinstance(row, dict):
                continue
            candidate = row.get("candidate")
            rows.append(candidate if isinstance(candidate, dict) else row)
    return rows


def _source_consensus_key(row: dict[str, Any]) -> tuple[str, str] | None:
    ticker = str(row.get("ticker") or "").upper()
    raw_date = row.get("signal_date") or row.get("date") or row.get("created_asof")
    if not ticker or not raw_date:
        return None
    return _date10(str(raw_date)), ticker


def _apply_source_consensus_support(
    candidate: dict[str, Any],
    source_consensus_by_key: dict[tuple[str, str], set[str]],
    config: dict[str, Any],
) -> None:
    key = _source_consensus_key(candidate)
    sources = sorted(source_consensus_by_key.get(key, set())) if key else []
    enabled = bool(config.get("source_consensus_enabled", True))
    support_applied = enabled and bool(sources)
    base_notional = float(config["paper_notional_usd"])
    scalar = float(config["source_consensus_notional_scalar"]) if support_applied else 1.0
    supported_notional = round(base_notional * scalar, 2)
    candidate.update(
        {
            "source_consensus_rule_version": SOURCE_CONSENSUS_RULE_VERSION,
            "source_consensus_support_applied": support_applied,
            "source_consensus_sources": sources,
            "source_consensus_notional_scalar": _round(scalar, 6),
            "source_consensus_paper_notional_usd": supported_notional,
            "source_consensus_known_at": (
                "after_signal_date_close_before_next_open_paper_entry"
            ),
        }
    )
    if support_applied:
        candidate["paper_notional_usd"] = supported_notional
        candidate["intended_notional"] = supported_notional


def _source_consensus_support_summary(
    candidates: list[dict[str, Any]],
    source_consensus_by_key: dict[tuple[str, str], set[str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    supported = [
        row for row in candidates if row.get("source_consensus_support_applied")
    ]
    source_counts: dict[str, int] = {}
    for row in supported:
        for source_name in row.get("source_consensus_sources") or []:
            source_counts[source_name] = source_counts.get(source_name, 0) + 1
    base_notional = float(config["paper_notional_usd"])
    scalar = float(config["source_consensus_notional_scalar"])
    return {
        "rule_version": SOURCE_CONSENSUS_RULE_VERSION,
        "enabled": bool(config.get("source_consensus_enabled", True)),
        "source_names": list(config.get("source_consensus_sources") or []),
        "source_key_count": len(source_consensus_by_key),
        "candidate_count": len(candidates),
        "supported_candidate_count": len(supported),
        "source_counts": dict(sorted(source_counts.items())),
        "base_paper_notional_usd": base_notional,
        "notional_scalar": scalar,
        "supported_paper_notional_usd": round(base_notional * scalar, 2),
        "trade_enabled": False,
        "alters_orders": False,
    }


def build_alpha_score_market_regime_context(
    ohlcv_by_ticker: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    spy_rows = rows_by_ticker.get("SPY") or []
    iwm_rows = rows_by_ticker.get("IWM") or []
    spy_idx = _index_on_date(spy_rows, as_of_date)
    iwm_idx = _index_on_date(iwm_rows, as_of_date)
    has_exact = spy_idx is not None and iwm_idx is not None
    ma_days = int(cfg["spy_ma_days"])
    ret_days = int(cfg["market_ret_days"])
    reason = "passed"
    spy_close = spy_ma = spy_ret = iwm_ret = iwm_minus_spy = None
    spy_above = False

    if not spy_rows or not iwm_rows:
        reason = "missing_spy_or_iwm_ohlcv"
    elif not has_exact:
        reason = "missing_exact_asof_benchmark_price"
    elif spy_idx < max(ma_days, ret_days) or iwm_idx < ret_days:
        reason = "insufficient_benchmark_history"
    else:
        spy_close = _positive_float(spy_rows[spy_idx].get("close"))
        spy_ma = _prior_average(spy_rows, spy_idx, ma_days, "close")
        spy_ret = _close_return(spy_rows, spy_idx - ret_days, spy_idx)
        iwm_ret = _close_return(iwm_rows, iwm_idx - ret_days, iwm_idx)
        if spy_close is None or spy_ma is None or spy_ret is None or iwm_ret is None:
            reason = "insufficient_benchmark_history"
        else:
            spy_above = spy_close >= spy_ma
            iwm_minus_spy = iwm_ret - spy_ret
            if not spy_above:
                reason = "spy_below_50d_ma"
            elif iwm_minus_spy < float(cfg["min_iwm_minus_spy_ret20"]):
                reason = "iwm_lagging_spy_20d"

    passed = reason == "passed"
    return {
        "rule_version": MARKET_REGIME_RULE_VERSION,
        "asof_date": as_of_date,
        "passed": passed,
        "status": "passed" if passed else "failed",
        "reason": reason,
        "has_exact_benchmark_price": bool(has_exact),
        "spy_above_50d_ma": bool(spy_above),
        "spy_close": _round(spy_close, 4),
        "spy_50d_ma": _round(spy_ma, 4),
        "spy_pct_from_50d_ma": _round(
            (spy_close / spy_ma) - 1.0 if spy_close and spy_ma else None,
            6,
        ),
        "spy_ret20": _round(spy_ret, 6),
        "iwm_ret20": _round(iwm_ret, 6),
        "iwm_minus_spy_ret20": _round(iwm_minus_spy, 6),
        "min_iwm_minus_spy_ret20": float(cfg["min_iwm_minus_spy_ret20"]),
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def build_alpha_score_market_regime_replacement_value_report(
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
    top_positive_share = (
        max(
            (
                float(row.get("positive_pnl_share") or 0.0)
                for row in by_ticker.values()
            ),
            default=0.0,
        )
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
        "top_ticker_positive_pnl_share": top_positive_share,
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


def _candidate_from_ranked_row(
    ranked: dict[str, Any],
    *,
    ticker: str,
    rank: int,
    rank_pct: float,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker) or []
    idx = _index_on_date(rows, as_of)
    if idx is None:
        return None
    close = _positive_float(rows[idx].get("close"))
    high = _positive_float(rows[idx].get("high"))
    low = _positive_float(rows[idx].get("low"))
    volume = _positive_float(rows[idx].get("volume"))
    if close is None or volume is None:
        return None
    avg_dollar_volume = _average_dollar_volume(
        rows,
        idx,
        int(config["avg_dollar_volume_days"]),
    )
    if (
        avg_dollar_volume is None
        or avg_dollar_volume < float(config["min_avg_dollar_volume_20d"])
    ):
        return None
    safe_notional = float(config["paper_notional_usd"])
    baseline_notional = float(config["baseline_paper_notional_usd"])
    return {
        "date": as_of,
        "signal_date": as_of,
        "ticker": ticker,
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "strategy": "full_universe_alpha_score_market_regime_safe_notional",
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "market_regime_rule_version": MARKET_REGIME_RULE_VERSION,
        "safe_notional_rule_version": SAFE_NOTIONAL_RULE_VERSION,
        "close": _round(close, 4),
        "signal_day_high": _round(high, 4),
        "signal_day_low": _round(low, 4),
        "signal_close_location": _round(
            _close_location_value(close=close, high=high, low=low),
            6,
        ),
        "entry_price": _round(close, 4),
        "alpha_score": _round(ranked.get("alpha_score"), 6),
        "alpha_score_rank": rank,
        "alpha_score_rank_pct": _round(rank_pct, 6),
        "alpha_score_bucket": _rank_bucket(rank_pct),
        "alpha_score_components": deepcopy(ranked.get("components") or {}),
        "rank_score_validity_regime_bucket": "valid_top_decile_market_regime_candidate",
        "breakout_20d": bool(ranked.get("breakout_20d")),
        "trend_score": _round(ranked.get("trend_score"), 6),
        "momentum_20d_pct": _round(ranked.get("momentum_20d_pct"), 6),
        "momentum_60d_pct": _round(ranked.get("momentum_60d_pct"), 6),
        "themes": list(ranked.get("themes") or []),
        "volume": _round(volume, 2),
        "avg_dollar_volume_20d": _round(avg_dollar_volume, 2),
        "source_universe": "current_production_universe_alpha_score_surface",
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "same_day_core_entry_count": 0,
        "same_day_core_overlap": False,
        "same_ticker_core_overlap": False,
        "baseline_paper_notional_usd": baseline_notional,
        "safe_paper_notional_usd": safe_notional,
        "safe_notional_scalar": _round(
            safe_notional / baseline_notional if baseline_notional else None,
            6,
        ),
        "paper_notional_usd": safe_notional,
        "intended_notional": safe_notional,
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
            "strategy": "full_universe_alpha_score_market_regime_safe_notional",
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


def _normalise_candidate_universe(
    value: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(value, list):
        return {
            "status": "provided",
            "tickers": sorted({str(item).upper() for item in value if item}),
            "records": {},
        }
    if isinstance(value, dict):
        records = value.get("records") if isinstance(value.get("records"), dict) else {}
        tickers = {str(item).upper() for item in value.get("tickers") or [] if item}
        tickers.update(str(key).upper() for key in records)
        return {
            "status": value.get("status") or "provided",
            "path": value.get("path"),
            "tickers": sorted(tickers),
            "records": {
                str(key).upper(): dict(row or {})
                for key, row in records.items()
                if key
            },
        }
    return {
        "status": "default_rows_by_ticker",
        "tickers": sorted(ticker for ticker in rows_by_ticker if ticker not in EXCLUDED_TICKERS),
        "records": {},
    }


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


def _exact_asof_price_maps(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    as_of: str,
    current_prices: dict[str, Any] | None,
    open_prices: dict[str, Any] | None,
) -> tuple[dict[str, float], dict[str, float]]:
    exact_current = {
        ticker: rows[idx]["close"]
        for ticker, rows in rows_by_ticker.items()
        for idx in [_index_on_date(rows, as_of)]
        if idx is not None and _positive_float(rows[idx].get("close")) is not None
    }
    exact_opens = {
        ticker: rows[idx]["open"]
        for ticker, rows in rows_by_ticker.items()
        for idx in [_index_on_date(rows, as_of)]
        if idx is not None and _positive_float(rows[idx].get("open")) is not None
    }
    provided_current = _normalise_prices(current_prices)
    provided_opens = _normalise_prices(open_prices)
    current = {
        **exact_current,
        **{
            ticker: value
            for ticker, value in provided_current.items()
            if ticker in exact_current
        },
    }
    opens = {
        **exact_opens,
        **{
            ticker: value
            for ticker, value in provided_opens.items()
            if ticker in exact_opens
        },
    }
    return current, opens


def _average_dollar_volume(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
) -> float | None:
    if idx < days:
        return None
    values = []
    for row in rows[idx - days:idx]:
        close = _positive_float(row.get("close"))
        volume = _positive_float(row.get("volume"))
        if close is not None and volume is not None:
            values.append(close * volume)
    if len(values) < days:
        return None
    return sum(values) / len(values)


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


def _rank_bucket(rank_pct: float | None) -> str:
    if rank_pct is None:
        return "unranked"
    if rank_pct <= 0.10:
        return "top_decile"
    if rank_pct <= 0.25:
        return "top_quartile"
    if rank_pct <= 0.50:
        return "top_half"
    return "bottom_half"


def _ranking_surface_summary(
    *,
    surface: dict[str, Any],
    ranked_rows: list[dict[str, Any]],
    threshold: float,
    top_decile_count: int,
) -> dict[str, Any]:
    leaders = []
    total = len(ranked_rows)
    for rank, row in enumerate(ranked_rows[:25], start=1):
        rank_pct = rank / total if total else None
        leaders.append(
            {
                "ticker": row.get("ticker"),
                "alpha_score": row.get("alpha_score"),
                "alpha_score_rank": rank,
                "alpha_score_rank_pct": _round(rank_pct, 6),
                "alpha_score_bucket": _rank_bucket(rank_pct),
                "components": deepcopy(row.get("components") or {}),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    return {
        "schema_version": 1,
        "source_surface_schema_version": surface.get("schema_version"),
        "source_rule_version": SOURCE_RULE_VERSION,
        "read_only": True,
        "weights": deepcopy(surface.get("weights") or {}),
        "universe_count": surface.get("universe_count"),
        "candidate_source_ticker_count": total,
        "ranked_count": total,
        "top_decile_threshold": threshold,
        "top_decile_count": top_decile_count,
        "leaders": leaders,
        "distribution": deepcopy(surface.get("distribution") or {}),
        "trade_enabled": False,
        "alters_orders": False,
    }


def prep_and_build_alpha_score_market_regime_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_dict: dict,
    spy_ohlcv=None,
    cached_ohlcv_fn=None,
    features_by_ticker=None,
    source_consensus_snapshots=None,
    open_prices=None,
    current_prices=None,
) -> tuple:
    """OHLCV + universe prep, then build. Returns (snapshot, ohlcv, universe)."""
    ohlcv = dict(ohlcv_dict)
    if spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    if cached_ohlcv_fn and ("IWM" not in ohlcv or ohlcv.get("IWM") is None):
        ohlcv["IWM"] = cached_ohlcv_fn("IWM")
    candidate_universe = {
        "status": "daily_data_universe",
        "tickers": sorted(
            t
            for t, f in ohlcv.items()
            if f is not None and str(t).upper() not in {"SPY", "IWM"}
        ),
    }
    snapshot = build_alpha_score_market_regime_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=features_by_ticker,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=candidate_universe,
        source_consensus_snapshots=source_consensus_snapshots,
        open_prices=open_prices,
        current_prices=current_prices,
    )
    return snapshot, ohlcv, candidate_universe


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
        "scope": "default_off_alpha_score_market_regime_paper_attribution",
    }
