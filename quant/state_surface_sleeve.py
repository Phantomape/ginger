"""Default-off state-surface satellite paper sleeve.

The state-surface satellite is an alpha observation surface, not a trading
rule. It scores current production-universe names with the same state-aware
cross-sectional features used in exp-20260507-016, then tracks a bounded paper
ledger. It never emits orders, changes core ranking, sizes positions, or
consumes A/B slots.
"""

from __future__ import annotations

import json
import math
import statistics
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_paths import data_artifact_path

try:
    from constants import ROUND_TRIP_COST_PCT
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT

try:
    from regime_engine import classify_market_regime
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.regime_engine import classify_market_regime

try:
    from evaluator_gates import GateThresholds, evaluate_metrics
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.evaluator_gates import GateThresholds, evaluate_metrics


SLEEVE_NAME = "STATE_SURFACE_SATELLITE_PAPER"
QUEUE_NAME = "STATE_SURFACE_SATELLITE_QUEUE"
RULE_VERSION = "state_surface_full_v1"
BENCHMARK_MOMENTUM_GATE_RULE_VERSION = "state_surface_benchmark_momentum_gate_v1"
RET20_EXCESS_SPY_GATE_RULE_VERSION = "state_surface_ret20_excess_spy_gate_v1"
RANK_NOTIONAL_RULE_VERSION = "state_surface_rank_notional_v2"
RANK_NOTIONAL_REGIME_RULE_VERSION = "state_surface_regime_rank_notional_v1"
RANK_NOTIONAL_CANDIDATE_BREADTH_RULE_VERSION = (
    "state_surface_candidate_breadth_rank_notional_v1"
)
RANK_NOTIONAL_SCORE_COMPRESSION_RULE_VERSION = (
    "state_surface_score_compression_rank_notional_v1"
)
STATE_SCHEMA_VERSION = 1
INDEX_TICKERS = {"SPY", "QQQ", "IWM"}

DEFAULT_STATE_PATH = data_artifact_path("state_surface_sleeve_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("state_surface_sleeve_paper_snapshots")

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "allowed_surfaces": ["rotation_breakout_leadership"],
    "max_candidates": 5,
    "max_positions": 3,
    "event_notional_usd": 10_000.0,
    "rank_notional_multipliers": [1.5, 1.25, 1.0, 0.75, 0.5],
    "rank_notional_regime_profiles_enabled": True,
    "rank_notional_regime_profiles": {
        "chop": [1.625, 1.3, 1.0, 0.7, 0.375],
    },
    "rank_notional_candidate_breadth_profiles_enabled": True,
    "rank_notional_candidate_breadth_min": 4,
    "rank_notional_candidate_breadth_profile": [1.6625, 1.315, 1.0, 0.675, 0.35],
    "rank_notional_score_compression_profiles_enabled": True,
    "rank_notional_score_compression_min_candidate_breadth": 3,
    "rank_notional_score_compression_max_top3_spread": 0.40,
    "rank_notional_score_compression_profile": [1.35, 1.45, 1.05, 0.675, 0.35],
    "hold_days": 20,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "fill_price_policy": "pending_next_session_open_when_available",
    "forward_gate_min_closed_trades": 15,
    "forward_gate_min_win_rate": 0.55,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_max_top_5_contribution_pct": 0.60,
    "forward_gate_max_hhi_concentration": 0.35,
    "benchmark_momentum_gate_enabled": True,
    "benchmark_momentum_gate_min_return": 0.0,
    "ret20_excess_spy_gate_enabled": True,
    "ret20_excess_spy_min": 0.0,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_state_surface_queue(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "queue_name": QUEUE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "candidates": [],
        "scored_candidate_count": 0,
        "scored_candidates": [],
        "blocked_candidate_count": 0,
        "blocked_candidates": [],
        "surface_blocked_candidate_count": 0,
        "surface_blocked_candidates": [],
        "surface_eligibility": _surface_eligibility_payload(DEFAULT_CONFIG),
        "ret20_excess_spy_gate": _ret20_excess_spy_gate_payload(DEFAULT_CONFIG),
        "rank_notional_profile": _rank_notional_profile_payload(DEFAULT_CONFIG),
        "market_regime": _market_regime_for_state({}, signal_count=0),
        "benchmark_momentum_gate": _blocked_benchmark_momentum_gate(reason),
        "state": {},
        "data_source": {"status": reason},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_state_surface_queue(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    universe: list[str] | None = None,
    core_signals: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    as_of_date = str(as_of)[:10]
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    spy_rows = rows_by_ticker.get("SPY") or []
    decision_date = _latest_date_on_or_before(spy_rows, as_of_date)
    if not decision_date:
        return empty_state_surface_queue(as_of_date, "missing_spy_decision_date")

    tickers = sorted(
        str(ticker).upper()
        for ticker in (universe or list(rows_by_ticker))
        if str(ticker).upper() not in INDEX_TICKERS
        and rows_by_ticker.get(str(ticker).upper())
    )
    if not tickers:
        return empty_state_surface_queue(as_of_date, "empty_state_surface_universe")

    state = _state_for_date(rows_by_ticker, tickers, decision_date)
    ranked = _score_candidates_for_date(rows_by_ticker, tickers, decision_date, state)
    core_tickers = {
        str(signal.get("ticker") or "").upper()
        for signal in (core_signals or [])
        if signal.get("ticker")
    }
    scored_candidates = [
        _candidate_payload(
            row,
            rank=idx + 1,
            as_of=as_of_date,
            decision_date=decision_date,
            core_signals=core_signals or [],
            config=cfg,
        )
        for idx, row in enumerate(ranked)
    ]
    benchmark_momentum_gate = evaluate_benchmark_momentum_gate(state, cfg)
    for row in scored_candidates:
        row["benchmark_momentum_gate"] = deepcopy(benchmark_momentum_gate)
        row["ret20_excess_spy_gate"] = evaluate_ret20_excess_spy_gate(row, cfg)

    candidates = []
    blocked_candidates = []
    surface_blocked_candidates = []
    if benchmark_momentum_gate["allowed"]:
        for row in scored_candidates:
            ticker = str(row.get("ticker") or "").upper()
            if ticker in core_tickers:
                continue
            if not _surface_allowed(row, cfg):
                surface_blocked_candidates.append(
                    _surface_blocked_candidate_payload(row, cfg)
                )
                continue
            ret20_gate = row.get("ret20_excess_spy_gate") or evaluate_ret20_excess_spy_gate(row, cfg)
            if not ret20_gate["allowed"]:
                blocked_candidates.append(
                    _ret20_excess_spy_blocked_candidate_payload(row, cfg, ret20_gate)
                )
                continue
            candidate = deepcopy(row)
            candidate["queue_rank"] = len(candidates) + 1
            candidates.append(candidate)
            if len(candidates) >= int(cfg["max_candidates"]):
                break
    else:
        for row in scored_candidates:
            if not _surface_allowed(row, cfg):
                surface_blocked_candidates.append(
                    _surface_blocked_candidate_payload(row, cfg)
                )
                continue
            ret20_gate = row.get("ret20_excess_spy_gate") or evaluate_ret20_excess_spy_gate(row, cfg)
            if not ret20_gate["allowed"]:
                blocked_candidates.append(
                    _ret20_excess_spy_blocked_candidate_payload(row, cfg, ret20_gate)
                )
                if len(blocked_candidates) >= int(cfg["max_candidates"]):
                    break
                continue
            blocked_candidates.append(
                {
                    "ticker": str(row.get("ticker") or "").upper(),
                    "rank": row.get("rank"),
                    "score": row.get("score"),
                    "surface": row.get("surface"),
                    "reason": "benchmark_momentum_gate_blocked",
                    "benchmark_momentum_gate": deepcopy(benchmark_momentum_gate),
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )
            if len(blocked_candidates) >= int(cfg["max_candidates"]):
                break

    regime_signal_count = len(candidates) if candidates else len(blocked_candidates)
    market_regime = _market_regime_for_state(state, signal_count=regime_signal_count)
    candidate_breadth = len(candidates)
    score_dispersion = _score_dispersion_for_candidates(candidates)
    for candidate in candidates:
        candidate["candidate_breadth"] = candidate_breadth
        candidate.update(score_dispersion)
        _apply_rank_notional(candidate, cfg, market_regime=market_regime)

    return {
        "queue_name": QUEUE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "decision_date": decision_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "scored_candidate_count": len(scored_candidates),
        "scored_candidates": scored_candidates,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "blocked_candidate_count": len(blocked_candidates),
        "blocked_candidates": blocked_candidates,
        "surface_blocked_candidate_count": len(surface_blocked_candidates),
        "surface_blocked_candidates": surface_blocked_candidates,
        "surface_eligibility": _surface_eligibility_payload(cfg),
        "ret20_excess_spy_gate": _ret20_excess_spy_gate_payload(cfg),
        "rank_notional_profile": _rank_notional_profile_payload(cfg),
        "market_regime": market_regime,
        "benchmark_momentum_gate": benchmark_momentum_gate,
        "excluded_core_tickers": sorted(core_tickers),
        "state": state,
        "parameters": dict(cfg),
        "data_source": {
            "status": "loaded",
            "source": "ohlcv_by_ticker",
            "ticker_count": len(rows_by_ticker),
            "decision_date": decision_date,
        },
        "production_impact": _production_impact(),
    }


def empty_state_surface_sleeve_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_state_surface_sleeve_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_state_surface_sleeve_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_state_surface_sleeve_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_state_surface_sleeve_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_state_surface_sleeve_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True) + "\n")


def build_state_surface_sleeve_snapshot(
    *,
    state_surface_queue: dict[str, Any] | None,
    as_of: str,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    working_state = deepcopy(
        state if state is not None else load_state_surface_sleeve_state(state_path)
    )
    _normalise_state(working_state)

    as_of_date = str(as_of)[:10]
    opens = _normalise_prices(open_prices)
    closes = _normalise_prices(current_prices)
    closed_today = _advance_open_positions(
        working_state,
        as_of=as_of_date,
        current_prices=closes,
        config=cfg,
    )
    filled_today, skipped_today = _fill_pending_entries(
        working_state,
        as_of=as_of_date,
        open_prices=opens,
        current_prices=closes,
        config=cfg,
    )
    new_pending = _add_queue_candidates(
        working_state,
        state_surface_queue or {},
        as_of=as_of_date,
        config=cfg,
    )
    snapshot = _snapshot_payload(
        working_state,
        state_surface_queue or {},
        as_of=as_of_date,
        config=cfg,
        new_pending=new_pending,
        filled_today=filled_today,
        closed_today=closed_today,
        skipped_today=skipped_today,
    )
    if persist:
        save_state_surface_sleeve_state(working_state, state_path)
        append_state_surface_sleeve_snapshot(snapshot, snapshot_log_path)
    return snapshot


def empty_state_surface_sleeve_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "blocked_candidate_count": 0,
        "surface_blocked_candidate_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "benchmark_momentum_gate": _blocked_benchmark_momentum_gate(reason),
        "surface_eligibility": _surface_eligibility_payload(DEFAULT_CONFIG),
        "ret20_excess_spy_gate": _ret20_excess_spy_gate_payload(DEFAULT_CONFIG),
        "rank_notional_profile": _rank_notional_profile_payload(DEFAULT_CONFIG),
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "tail_diagnostics": build_state_surface_forward_tail_diagnostics([], DEFAULT_CONFIG),
        "data_source": {"status": reason},
        "production_impact": _production_impact(),
        "error": reason,
    }


def evaluate_benchmark_momentum_gate(
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    enabled = bool(cfg.get("benchmark_momentum_gate_enabled", True))
    threshold = float(cfg.get("benchmark_momentum_gate_min_return", 0.0))
    returns = {
        "SPY": _float_or_none(state.get("spy_ret20")),
        "QQQ": _float_or_none(state.get("qqq_ret20")),
    }
    available_returns = [value for value in returns.values() if value is not None]
    benchmark_return_max = max(available_returns) if available_returns else None

    reasons: list[str] = []
    if enabled:
        if benchmark_return_max is None:
            reasons.append("benchmark_momentum_unavailable")
        elif benchmark_return_max <= threshold:
            reasons.append("benchmark_momentum_nonpositive")

    allowed = (not enabled) or not reasons
    return {
        "rule_version": BENCHMARK_MOMENTUM_GATE_RULE_VERSION,
        "enabled": enabled,
        "allowed": allowed,
        "status": "allowed" if allowed else "blocked",
        "reasons": reasons,
        "benchmark_returns_20d": {key: _round(value, 6) for key, value in returns.items()},
        "benchmark_return_max_20d": _round(benchmark_return_max, 6),
        "threshold": _round(threshold, 6),
        "scope": "default_off_state_surface_paper_candidate_queue",
        "trade_enabled_after_gate": False,
        "production_impact": _production_impact(),
    }


def evaluate_ret20_excess_spy_gate(
    candidate: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    enabled = bool(cfg.get("ret20_excess_spy_gate_enabled", True))
    threshold = float(cfg.get("ret20_excess_spy_min", 0.0))
    features = candidate.get("features") or {}
    ret20_excess_spy = _float_or_none(features.get("ret20_excess_spy"))

    reasons: list[str] = []
    if enabled:
        if ret20_excess_spy is None:
            reasons.append("ret20_excess_spy_unavailable")
        elif ret20_excess_spy < threshold:
            reasons.append("ret20_excess_spy_below_floor")

    allowed = (not enabled) or not reasons
    return {
        "rule_version": RET20_EXCESS_SPY_GATE_RULE_VERSION,
        "enabled": enabled,
        "allowed": allowed,
        "status": "allowed" if allowed else "blocked",
        "reasons": reasons,
        "ret20_excess_spy": _round(ret20_excess_spy, 6),
        "threshold": _round(threshold, 6),
        "scope": "default_off_state_surface_paper_candidate_queue",
        "trade_enabled_after_gate": False,
        "production_impact": _production_impact(),
    }


def _blocked_benchmark_momentum_gate(reason: str) -> dict[str, Any]:
    return {
        "rule_version": BENCHMARK_MOMENTUM_GATE_RULE_VERSION,
        "enabled": True,
        "allowed": False,
        "status": "blocked",
        "reasons": [reason],
        "benchmark_returns_20d": {"SPY": None, "QQQ": None},
        "benchmark_return_max_20d": None,
        "threshold": _round(DEFAULT_CONFIG["benchmark_momentum_gate_min_return"], 6),
        "scope": "default_off_state_surface_paper_candidate_queue",
        "trade_enabled_after_gate": False,
        "production_impact": _production_impact(),
    }


def _ret20_excess_spy_gate_payload(config: dict[str, Any]) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    return {
        "rule_version": RET20_EXCESS_SPY_GATE_RULE_VERSION,
        "enabled": bool(cfg.get("ret20_excess_spy_gate_enabled", True)),
        "threshold": _round(float(cfg.get("ret20_excess_spy_min", 0.0)), 6),
        "scope": "default_off_state_surface_paper_candidate_queue",
        "trade_enabled_after_gate": False,
        "production_impact": _production_impact(),
    }


def _positive_float_list(raw: Any) -> list[float]:
    values: list[float] = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            parsed = _float_or_none(item)
            if parsed is not None and parsed > 0:
                values.append(parsed)
    return values


def _rank_notional_multipliers(config: dict[str, Any]) -> list[float]:
    return _positive_float_list(config.get("rank_notional_multipliers"))


def _rank_notional_regime_profiles(config: dict[str, Any]) -> dict[str, list[float]]:
    raw = config.get("rank_notional_regime_profiles")
    if not isinstance(raw, dict):
        return {}
    profiles: dict[str, list[float]] = {}
    for regime, values in raw.items():
        profile = _positive_float_list(values)
        if profile:
            profiles[str(regime)] = profile
    return profiles


def _rank_notional_candidate_breadth_profile(config: dict[str, Any]) -> list[float]:
    return _positive_float_list(config.get("rank_notional_candidate_breadth_profile"))


def _rank_notional_score_compression_profile(config: dict[str, Any]) -> list[float]:
    return _positive_float_list(config.get("rank_notional_score_compression_profile"))


def _score_compression_profile_name(threshold: float) -> str:
    value = str(round(float(threshold), 6)).rstrip("0").rstrip(".")
    return f"score_compression_top3_le_{value.replace('.', 'p')}"


def _score_compression_profile_applies(
    config: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> tuple[str | None, list[float] | None]:
    if not bool(config.get("rank_notional_score_compression_profiles_enabled", True)):
        return None, None
    row = candidate or {}
    candidate_breadth = _float_or_none(row.get("candidate_breadth"))
    min_breadth = _float_or_none(
        config.get("rank_notional_score_compression_min_candidate_breadth")
    )
    top3_spread = _float_or_none(row.get("score_top3_spread"))
    max_spread = _float_or_none(
        config.get("rank_notional_score_compression_max_top3_spread")
    )
    profile = _rank_notional_score_compression_profile(config)
    if (
        candidate_breadth is not None
        and min_breadth is not None
        and top3_spread is not None
        and max_spread is not None
        and candidate_breadth >= min_breadth
        and top3_spread <= max_spread
        and profile
    ):
        return _score_compression_profile_name(max_spread), profile
    return None, None


def _rank_notional_profile_for_regime(
    config: dict[str, Any],
    market_regime: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
) -> tuple[str, list[float]]:
    compression_name, compression_profile = _score_compression_profile_applies(
        config,
        candidate,
    )
    if compression_name and compression_profile:
        return compression_name, compression_profile

    if bool(config.get("rank_notional_candidate_breadth_profiles_enabled", True)):
        candidate_breadth = _float_or_none((candidate or {}).get("candidate_breadth"))
        min_breadth = _float_or_none(
            config.get("rank_notional_candidate_breadth_min")
        )
        breadth_profile = _rank_notional_candidate_breadth_profile(config)
        if (
            candidate_breadth is not None
            and min_breadth is not None
            and candidate_breadth >= min_breadth
            and breadth_profile
        ):
            return "candidate_breadth_ge4_override", breadth_profile

    values = _rank_notional_multipliers(config)
    if not bool(config.get("rank_notional_regime_profiles_enabled", True)):
        return "default", values
    regime = str((market_regime or {}).get("regime") or "")
    profiles = _rank_notional_regime_profiles(config)
    override = profiles.get(regime)
    if override:
        return f"{regime}_override", override
    return "default", values


def _rank_notional_multiplier(
    queue_rank: Any,
    config: dict[str, Any],
    market_regime: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
) -> float:
    _, values = _rank_notional_profile_for_regime(
        config,
        market_regime,
        candidate,
    )
    if not values:
        return 1.0
    try:
        rank = int(queue_rank)
    except (TypeError, ValueError):
        rank = 1
    if rank <= 0:
        rank = 1
    if rank > len(values):
        return values[-1]
    return values[rank - 1]


def _event_notional_for_queue_rank(
    queue_rank: Any,
    config: dict[str, Any],
    market_regime: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
) -> float:
    base_notional = float(config.get("event_notional_usd") or 0.0)
    return round(
        base_notional
        * _rank_notional_multiplier(queue_rank, config, market_regime, candidate),
        2,
    )


def _apply_rank_notional(
    candidate: dict[str, Any],
    config: dict[str, Any],
    market_regime: dict[str, Any] | None = None,
) -> None:
    queue_rank = candidate.get("queue_rank")
    profile_name, _ = _rank_notional_profile_for_regime(
        config,
        market_regime,
        candidate,
    )
    multiplier = _rank_notional_multiplier(queue_rank, config, market_regime, candidate)
    candidate["rank_notional_multiplier"] = _round(multiplier, 6)
    candidate["event_notional_usd"] = _event_notional_for_queue_rank(
        queue_rank,
        config,
        market_regime,
        candidate,
    )
    candidate["rank_notional_rule_version"] = RANK_NOTIONAL_RULE_VERSION
    candidate["rank_notional_regime_rule_version"] = RANK_NOTIONAL_REGIME_RULE_VERSION
    candidate["rank_notional_candidate_breadth_rule_version"] = (
        RANK_NOTIONAL_CANDIDATE_BREADTH_RULE_VERSION
    )
    candidate["rank_notional_score_compression_rule_version"] = (
        RANK_NOTIONAL_SCORE_COMPRESSION_RULE_VERSION
    )
    candidate["rank_notional_profile_name"] = profile_name
    candidate["market_regime"] = deepcopy(market_regime or {})


def _entry_event_notional(entry: dict[str, Any], config: dict[str, Any]) -> float:
    parsed = _float_or_none(entry.get("event_notional_usd"))
    if parsed is not None and parsed > 0:
        return parsed
    return _event_notional_for_queue_rank(
        entry.get("queue_rank"),
        config,
        entry.get("market_regime") or None,
        entry,
    )


def _rank_notional_profile_payload(config: dict[str, Any]) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    values = _rank_notional_multipliers(cfg)
    regime_profiles = _rank_notional_regime_profiles(cfg)
    breadth_profile = _rank_notional_candidate_breadth_profile(cfg)
    score_profile = _rank_notional_score_compression_profile(cfg)
    base_notional = float(cfg.get("event_notional_usd") or 0.0)
    return {
        "rule_version": RANK_NOTIONAL_RULE_VERSION,
        "regime_rule_version": RANK_NOTIONAL_REGIME_RULE_VERSION,
        "candidate_breadth_rule_version": RANK_NOTIONAL_CANDIDATE_BREADTH_RULE_VERSION,
        "score_compression_rule_version": RANK_NOTIONAL_SCORE_COMPRESSION_RULE_VERSION,
        "base_event_notional_usd": _round(base_notional, 2),
        "rank_notional_multipliers": [_round(value, 6) for value in values],
        "rank_event_notional_usd": [
            _round(base_notional * value, 2) for value in values
        ],
        "regime_profiles_enabled": bool(
            cfg.get("rank_notional_regime_profiles_enabled", True)
        ),
        "regime_profiles": {
            regime: [_round(value, 6) for value in profile]
            for regime, profile in regime_profiles.items()
        },
        "regime_rank_event_notional_usd": {
            regime: [_round(base_notional * value, 2) for value in profile]
            for regime, profile in regime_profiles.items()
        },
        "candidate_breadth_profiles_enabled": bool(
            cfg.get("rank_notional_candidate_breadth_profiles_enabled", True)
        ),
        "candidate_breadth_min": _round(
            cfg.get("rank_notional_candidate_breadth_min"),
            6,
        ),
        "candidate_breadth_profile": [
            _round(value, 6) for value in breadth_profile
        ],
        "candidate_breadth_rank_event_notional_usd": [
            _round(base_notional * value, 2) for value in breadth_profile
        ],
        "score_compression_profiles_enabled": bool(
            cfg.get("rank_notional_score_compression_profiles_enabled", True)
        ),
        "score_compression_min_candidate_breadth": _round(
            cfg.get("rank_notional_score_compression_min_candidate_breadth"),
            6,
        ),
        "score_compression_max_top3_spread": _round(
            cfg.get("rank_notional_score_compression_max_top3_spread"),
            6,
        ),
        "score_compression_profile": [_round(value, 6) for value in score_profile],
        "score_compression_rank_event_notional_usd": [
            _round(base_notional * value, 2) for value in score_profile
        ],
        "scope": "default_off_state_surface_paper_candidate_queue",
        "trade_enabled_after_profile": False,
        "production_impact": _production_impact(),
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
    return sorted([row for row in rows if row.get("date")], key=lambda row: row["date"])


def _latest_date_on_or_before(rows: list[dict[str, Any]], as_of: str) -> str | None:
    dates = [str(row.get("date") or "") for row in rows if str(row.get("date") or "") <= as_of]
    return max(dates) if dates else None


def _close(row: dict[str, Any]) -> float | None:
    value = _float_or_none(row.get("close"))
    return value if value and value > 0 else None


def _volume(row: dict[str, Any]) -> float | None:
    value = _float_or_none(row.get("volume"))
    return value if value and value > 0 else None


def _rows_until(rows: list[dict[str, Any]], date_str: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("date") or "") <= date_str]


def _ret(rows: list[dict[str, Any]], date_str: str, lookback: int) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) <= lookback:
        return None
    now = _close(hist[-1])
    then = _close(hist[-lookback - 1])
    if not now or not then:
        return None
    return now / then - 1.0


def _pct_from_sma(rows: list[dict[str, Any]], date_str: str, lookback: int) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback:
        return None
    now = _close(hist[-1])
    closes = [_close(row) for row in hist[-lookback:]]
    closes = [value for value in closes if value]
    if not now or len(closes) < lookback:
        return None
    avg = sum(closes) / len(closes)
    return now / avg - 1.0 if avg else None


def _volume_ratio(rows: list[dict[str, Any]], date_str: str, lookback: int = 20) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback + 1:
        return None
    now = _volume(hist[-1])
    vols = [_volume(row) for row in hist[-lookback - 1 : -1]]
    vols = [value for value in vols if value]
    if not now or len(vols) < lookback:
        return None
    avg = sum(vols) / len(vols)
    return now / avg if avg else None


def _near_high(rows: list[dict[str, Any]], date_str: str, lookback: int = 60) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback:
        return None
    now = _close(hist[-1])
    highs = [_float_or_none(row.get("high")) for row in hist[-lookback:]]
    highs = [value for value in highs if value]
    if not now or not highs:
        return None
    high = max(highs)
    return now / high if high else None


def _breadth(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
    lookback: int,
) -> float | None:
    seen = 0
    above = 0
    for ticker in universe:
        pct = _pct_from_sma(ohlcv.get(ticker.upper()) or [], date_str, lookback)
        if pct is None:
            continue
        seen += 1
        above += int(pct > 0)
    return above / seen if seen else None


def _sector_dispersion(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
) -> float | None:
    # exp-20260507-016 did not have point-in-time sector buckets for this
    # surface, so dispersion stayed unavailable and only the validated
    # balanced/breadth/rotation surfaces were eligible.
    return None


def _state_for_date(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
) -> dict[str, Any]:
    spy_ret10 = _ret(ohlcv.get("SPY") or [], date_str, 10)
    qqq_ret10 = _ret(ohlcv.get("QQQ") or [], date_str, 10)
    spy_ret20 = _ret(ohlcv.get("SPY") or [], date_str, 20)
    qqq_ret20 = _ret(ohlcv.get("QQQ") or [], date_str, 20)
    iwm_ret20 = _ret(ohlcv.get("IWM") or [], date_str, 20)
    spy_pct200 = _pct_from_sma(ohlcv.get("SPY") or [], date_str, 200)
    qqq_pct200 = _pct_from_sma(ohlcv.get("QQQ") or [], date_str, 200)
    breadth50 = _breadth(ohlcv, universe, date_str, 50)
    dispersion20 = _sector_dispersion(ohlcv, universe, date_str)

    pct_values = [value for value in (spy_pct200, qqq_pct200) if value is not None]
    min_index_pct200 = min(pct_values) if pct_values else None
    qqq_minus_iwm = qqq_ret20 - iwm_ret20 if qqq_ret20 is not None and iwm_ret20 is not None else None
    qqq_minus_spy = qqq_ret20 - spy_ret20 if qqq_ret20 is not None and spy_ret20 is not None else None
    iwm_minus_spy = iwm_ret20 - spy_ret20 if iwm_ret20 is not None and spy_ret20 is not None else None

    if min_index_pct200 is not None and min_index_pct200 < 0:
        state_bucket = "weak_index"
    elif qqq_minus_iwm is not None and qqq_minus_iwm > 0.04:
        state_bucket = "narrow_cap_weight_leadership"
    elif iwm_minus_spy is not None and iwm_minus_spy > 0.02:
        state_bucket = "broad_rotation"
    else:
        state_bucket = "balanced_risk_on"

    if breadth50 is None:
        breadth_bucket = "unknown"
    elif breadth50 >= 0.65:
        breadth_bucket = "broad_breadth"
    elif breadth50 <= 0.45:
        breadth_bucket = "thin_breadth"
    else:
        breadth_bucket = "mixed_breadth"

    if dispersion20 is None:
        dispersion_bucket = "unknown"
    elif dispersion20 >= 0.08:
        dispersion_bucket = "high_sector_dispersion"
    elif dispersion20 <= 0.035:
        dispersion_bucket = "low_sector_dispersion"
    else:
        dispersion_bucket = "mid_sector_dispersion"

    return {
        "state_bucket": state_bucket,
        "breadth_bucket": breadth_bucket,
        "dispersion_bucket": dispersion_bucket,
        "spy_ret10": _round(spy_ret10, 6),
        "qqq_ret10": _round(qqq_ret10, 6),
        "spy_ret20": _round(spy_ret20, 6),
        "qqq_ret20": _round(qqq_ret20, 6),
        "iwm_ret20": _round(iwm_ret20, 6),
        "qqq_minus_spy_ret20": _round(qqq_minus_spy, 6),
        "qqq_minus_iwm_ret20": _round(qqq_minus_iwm, 6),
        "iwm_minus_spy_ret20": _round(iwm_minus_spy, 6),
        "spy_pct_from_200sma": _round(spy_pct200, 6),
        "qqq_pct_from_200sma": _round(qqq_pct200, 6),
        "min_index_pct_from_200sma": _round(min_index_pct200, 6),
        "universe_breadth_above_50sma": _round(breadth50, 6),
        "sector_ret20_dispersion": _round(dispersion20, 6),
    }


def _market_regime_for_state(
    state: dict[str, Any],
    *,
    signal_count: int,
) -> dict[str, Any]:
    context = {
        "spy_pct_from_ma": _float_or_none(state.get("spy_pct_from_200sma")),
        "qqq_pct_from_ma": _float_or_none(state.get("qqq_pct_from_200sma")),
        "spy_10d_return": _float_or_none(state.get("spy_ret10")),
        "qqq_10d_return": _float_or_none(state.get("qqq_ret10")),
        "spy_20d_return": _float_or_none(state.get("spy_ret20")),
        "qqq_20d_return": _float_or_none(state.get("qqq_ret20")),
        "qqq_minus_spy_ret20": _float_or_none(state.get("qqq_minus_spy_ret20")),
        "theme_signal_count": int(signal_count or 0),
        "breakout_signal_count": int(signal_count or 0),
    }
    report = deepcopy(classify_market_regime(context))
    report["rule_version"] = "regime_engine_classify_market_regime_v1"
    report["scope"] = "default_off_state_surface_paper_candidate_queue"
    report["production_impact"] = _production_impact()
    return report


def _score_candidates_for_date(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    features: dict[str, dict[str, float]] = {}
    for ticker in universe:
        rows = ohlcv.get(ticker.upper()) or []
        if date_str not in {str(row.get("date") or "") for row in rows}:
            continue
        ret20 = _ret(rows, date_str, 20)
        ret60 = _ret(rows, date_str, 60)
        ret5 = _ret(rows, date_str, 5)
        near_high = _near_high(rows, date_str, 60)
        vol_ratio = _volume_ratio(rows, date_str, 20)
        spy_ret20 = float(state.get("spy_ret20") or 0.0)
        if None in (ret20, ret60, ret5, near_high, vol_ratio):
            continue
        features[ticker.upper()] = {
            "ret20_excess_spy": float(ret20) - spy_ret20,
            "ret60": float(ret60),
            "ret5": float(ret5),
            "near_high_60": float(near_high),
            "volume_ratio_20": float(vol_ratio),
        }
    if not features:
        return []

    z_ret20 = _zscore_map({ticker: row["ret20_excess_spy"] for ticker, row in features.items()})
    z_ret60 = _zscore_map({ticker: row["ret60"] for ticker, row in features.items()})
    z_pause = _zscore_map({ticker: -abs(row["ret5"]) for ticker, row in features.items()})
    z_high = _zscore_map({ticker: row["near_high_60"] for ticker, row in features.items()})
    z_volume = _zscore_map({ticker: row["volume_ratio_20"] for ticker, row in features.items()})

    state_bucket = str(state.get("state_bucket") or "")
    breadth_bucket = str(state.get("breadth_bucket") or "")
    dispersion_bucket = str(state.get("dispersion_bucket") or "")
    candidates = []
    for ticker, values in features.items():
        if state_bucket == "broad_rotation":
            surface = "rotation_breakout_leadership"
            score = 0.45 * z_ret20[ticker] + 0.25 * z_high[ticker] + 0.20 * z_volume[ticker] + 0.10 * z_ret60[ticker]
        elif breadth_bucket == "broad_breadth":
            surface = "broad_breadth_trend_persistence"
            score = 0.40 * z_ret60[ticker] + 0.25 * z_ret20[ticker] + 0.20 * z_pause[ticker] + 0.15 * z_high[ticker]
        elif dispersion_bucket == "mid_sector_dispersion":
            surface = "mid_dispersion_selective_leadership"
            score = 0.35 * z_ret20[ticker] + 0.30 * z_ret60[ticker] + 0.20 * z_high[ticker] + 0.15 * z_volume[ticker]
        else:
            surface = "balanced_state_leadership"
            score = 0.35 * z_ret60[ticker] + 0.35 * z_ret20[ticker] + 0.20 * z_high[ticker] + 0.10 * z_pause[ticker]
        candidates.append(
            {
                "date": date_str,
                "ticker": ticker,
                "surface": surface,
                "score": _round(score, 6),
                "state_bucket": state_bucket,
                "breadth_bucket": breadth_bucket,
                "dispersion_bucket": dispersion_bucket,
                "features": {key: _round(value, 6) for key, value in values.items()},
            }
        )
    return sorted(candidates, key=lambda row: (row["score"], row["ticker"]), reverse=True)


def _zscore_map(values: dict[str, float]) -> dict[str, float]:
    clean = [value for value in values.values() if value is not None]
    if len(clean) < 2:
        return {key: 0.0 for key in values}
    mean = statistics.mean(clean)
    stdev = statistics.pstdev(clean) or 1.0
    return {key: (value - mean) / stdev for key, value in values.items()}


def _score_dispersion_for_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(candidates, key=_candidate_sort_key)
    scores = [_float_or_none(row.get("score")) for row in ranked[:3]]
    scores = [score for score in scores if score is not None]
    top_score = scores[0] if scores else None
    rank2_score = scores[1] if len(scores) >= 2 else None
    rank3_score = scores[2] if len(scores) >= 3 else None
    top_to_second = (
        float(top_score) - float(rank2_score)
        if top_score is not None and rank2_score is not None
        else None
    )
    top3_spread = (
        float(top_score) - float(rank3_score)
        if top_score is not None and rank3_score is not None
        else None
    )
    return {
        "score_top": _round(top_score, 6),
        "score_rank2": _round(rank2_score, 6),
        "score_rank3": _round(rank3_score, 6),
        "score_top_to_second_gap": _round(top_to_second, 6),
        "score_top3_spread": _round(top3_spread, 6),
        "score_dispersion_sample_size": len(scores),
    }


def _candidate_payload(
    row: dict[str, Any],
    *,
    rank: int,
    as_of: str,
    decision_date: str,
    core_signals: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    decision_id = f"{SLEEVE_NAME}:{RULE_VERSION}:{decision_date}:{rank}:{ticker}:{row.get('surface')}"
    return {
        **deepcopy(row),
        "source": "state_surface_satellite",
        "source_label": "State surface satellite",
        "rule_version": RULE_VERSION,
        "decision_id": decision_id,
        "rank": rank,
        "created_asof": as_of,
        "usable_trade_date": decision_date,
        "entry_date": decision_date,
        "intended_entry_timing": "next_session_open",
        "event_notional_usd": float(config["event_notional_usd"]),
        "hold_days": int(config["hold_days"]),
        "trade_enabled": False,
        "alters_orders": False,
        "counterfactuals": {
            "frozen_asof": as_of,
            "alternatives": _counterfactual_alternatives(core_signals),
        },
    }


def _allowed_surface_set(config: dict[str, Any]) -> set[str] | None:
    raw = config.get("allowed_surfaces")
    if raw in (None, "", []):
        return None
    if isinstance(raw, str):
        values = [raw]
    else:
        values = list(raw)
    allowed = {str(value) for value in values if str(value or "")}
    return allowed or None


def _surface_allowed(row: dict[str, Any], config: dict[str, Any]) -> bool:
    allowed = _allowed_surface_set(config)
    if allowed is None:
        return True
    return str(row.get("surface") or "") in allowed


def _surface_eligibility_payload(config: dict[str, Any]) -> dict[str, Any]:
    allowed = _allowed_surface_set(config)
    return {
        "rule_version": "state_surface_allowed_surfaces_v1",
        "allowed_surfaces": sorted(allowed) if allowed is not None else None,
        "scope": "default_off_state_surface_paper_candidate_queue",
        "trade_enabled_after_gate": False,
        "production_impact": _production_impact(),
    }


def _surface_blocked_candidate_payload(
    row: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "rank": row.get("rank"),
        "score": row.get("score"),
        "surface": row.get("surface"),
        "reason": "surface_not_allowed",
        "surface_eligibility": _surface_eligibility_payload(config),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _ret20_excess_spy_blocked_candidate_payload(
    row: dict[str, Any],
    config: dict[str, Any],
    gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = gate or evaluate_ret20_excess_spy_gate(row, config)
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "rank": row.get("rank"),
        "score": row.get("score"),
        "surface": row.get("surface"),
        "reason": "ret20_excess_spy_gate_blocked",
        "ret20_excess_spy_gate": deepcopy(payload),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _counterfactual_alternatives(core_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alternatives = []
    for signal in sorted(
        core_signals or [],
        key=lambda row: (
            -(float(row.get("trade_quality_score") or row.get("confidence_score") or 0.0)),
            str(row.get("ticker") or ""),
        ),
    )[:3]:
        alternatives.append(
            {
                "type": "core_signal",
                "ticker": str(signal.get("ticker") or "").upper(),
                "strategy": signal.get("strategy"),
                "confidence_score": signal.get("confidence_score"),
                "trade_quality_score": signal.get("trade_quality_score"),
                "alters_orders": False,
            }
        )
    alternatives.append({"type": "cash", "ticker": "CASH", "alters_orders": False})
    return alternatives


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_entries", [])


def _normalise_prices(prices: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, value in (prices or {}).items():
        parsed = _float_or_none(value)
        if parsed is not None and parsed > 0:
            out[str(ticker).upper()] = parsed
    return out


def _advance_open_positions(
    state: dict[str, Any],
    *,
    as_of: str,
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open = []
    closed_today = []
    hold_days = int(config["hold_days"])
    cost = float(config["round_trip_cost_pct"])
    for raw in state["open_positions"]:
        position = dict(raw)
        ticker = str(position.get("ticker") or "").upper()
        current = current_prices.get(ticker)
        if current is None:
            still_open.append(position)
            continue
        entry_date = str(position.get("entry_date") or "")[:10]
        last_seen = str(position.get("last_seen_date") or "")[:10]
        if as_of > entry_date and as_of != last_seen:
            position["observed_trading_days"] = int(position.get("observed_trading_days") or 0) + 1
        position["last_seen_date"] = as_of
        position["last_price"] = current
        _mark_unrealized(position, current, cost)
        if int(position.get("observed_trading_days") or 0) >= hold_days:
            closed = _close_position(position, current, as_of, cost)
            state["closed_positions"].append(closed)
            closed_today.append(closed)
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
    if not config.get("paper_enabled", True):
        return [], []
    remaining = []
    filled_today = []
    skipped_today = []
    max_positions = int(config["max_positions"])
    cost = float(config["round_trip_cost_pct"])
    for entry in sorted(state["pending_entries"], key=_pending_sort_key):
        if str(entry.get("created_asof") or "")[:10] >= as_of:
            remaining.append(entry)
            continue
        if len(state["open_positions"]) >= max_positions:
            skipped = {**entry, "status": "skipped_capacity_full", "skipped_asof": as_of, "trade_enabled": False}
            state["skipped_entries"].append(skipped)
            skipped_today.append(skipped)
            continue
        ticker = str(entry.get("ticker") or "").upper()
        entry_open = open_prices.get(ticker)
        if entry_open is None:
            entry["status"] = "pending_missing_entry_open_price"
            entry["last_checked_asof"] = as_of
            remaining.append(entry)
            continue
        notional = _entry_event_notional(entry, config)
        position = {
            "decision_id": entry["decision_id"],
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "surface": entry.get("surface"),
            "source_event_date": entry.get("source_event_date"),
            "entry_date": as_of,
            "entry_price": entry_open,
            "notional": notional,
            "shares": round(notional / entry_open, 8),
            "hold_days": int(config["hold_days"]),
            "candidate_breadth": entry.get("candidate_breadth"),
            "score_top3_spread": entry.get("score_top3_spread"),
            "score_top_to_second_gap": entry.get("score_top_to_second_gap"),
            "score_dispersion_sample_size": entry.get("score_dispersion_sample_size"),
            "candidate_breadth_profile_name": entry.get(
                "candidate_breadth_profile_name"
            ),
            "rank_notional_multiplier": _float_or_none(
                entry.get("rank_notional_multiplier")
            ),
            "rank_notional_profile_name": entry.get("rank_notional_profile_name"),
            "rank_notional_rule_version": entry.get("rank_notional_rule_version"),
            "rank_notional_regime_rule_version": entry.get(
                "rank_notional_regime_rule_version"
            ),
            "rank_notional_candidate_breadth_rule_version": entry.get(
                "rank_notional_candidate_breadth_rule_version"
            ),
            "rank_notional_score_compression_rule_version": entry.get(
                "rank_notional_score_compression_rule_version"
            ),
            "market_regime": deepcopy(entry.get("market_regime") or {}),
            "observed_trading_days": 0,
            "last_seen_date": as_of,
            "last_price": current_prices.get(ticker),
            "trade_enabled": False,
            "paper_status": "open",
            "source_candidate": entry.get("candidate") or {},
        }
        if position["last_price"] is not None:
            _mark_unrealized(position, float(position["last_price"]), cost)
        state["open_positions"].append(position)
        filled_today.append(position)
    state["pending_entries"] = remaining
    return filled_today, skipped_today


def _add_queue_candidates(
    state: dict[str, Any],
    queue: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not config.get("paper_enabled", True):
        return []
    existing = _existing_decision_ids(state)
    new_entries = []
    for candidate in sorted(queue.get("candidates") or [], key=_candidate_sort_key):
        decision_id = str(candidate.get("decision_id") or "")
        if not decision_id or decision_id in existing:
            continue
        entry = {
            "decision_id": decision_id,
            "sleeve": SLEEVE_NAME,
            "ticker": str(candidate.get("ticker") or "").upper(),
            "surface": candidate.get("surface"),
            "rank": candidate.get("rank"),
            "queue_rank": candidate.get("queue_rank"),
            "score": candidate.get("score"),
            "created_asof": as_of,
            "source_event_date": str(candidate.get("usable_trade_date") or "")[:10],
            "status": "pending_next_session_open",
            "intended_entry_timing": "next_session_open",
            "event_notional_usd": _float_or_none(candidate.get("event_notional_usd")),
            "candidate_breadth": candidate.get("candidate_breadth"),
            "score_top3_spread": candidate.get("score_top3_spread"),
            "score_top_to_second_gap": candidate.get("score_top_to_second_gap"),
            "score_dispersion_sample_size": candidate.get("score_dispersion_sample_size"),
            "candidate_breadth_profile_name": candidate.get(
                "rank_notional_profile_name"
            ),
            "rank_notional_candidate_breadth_rule_version": candidate.get(
                "rank_notional_candidate_breadth_rule_version"
            ),
            "rank_notional_score_compression_rule_version": candidate.get(
                "rank_notional_score_compression_rule_version"
            ),
            "rank_notional_multiplier": _float_or_none(
                candidate.get("rank_notional_multiplier")
            ),
            "rank_notional_profile_name": candidate.get("rank_notional_profile_name"),
            "rank_notional_rule_version": candidate.get("rank_notional_rule_version"),
            "rank_notional_regime_rule_version": candidate.get(
                "rank_notional_regime_rule_version"
            ),
            "market_regime": deepcopy(candidate.get("market_regime") or {}),
            "trade_enabled": False,
            "candidate": deepcopy(candidate),
        }
        state["pending_entries"].append(entry)
        new_entries.append(entry)
        existing.add(decision_id)
    return new_entries


def _snapshot_payload(
    state: dict[str, Any],
    queue: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
    new_pending: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    skipped_today: list[dict[str, Any]],
) -> dict[str, Any]:
    realized = round(sum(float(item.get("pnl") or 0.0) for item in state["closed_positions"]), 2)
    unrealized = round(sum(float(item.get("net_pnl_if_closed_now") or 0.0) for item in state["open_positions"]), 2)
    gate = _forward_paper_gate(state["closed_positions"], config)
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "asof_date": as_of,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(config.get("paper_enabled", True)),
        "trade_enabled": False,
        "candidate_count": int(queue.get("candidate_count") or 0),
        "blocked_candidate_count": int(queue.get("blocked_candidate_count") or 0),
        "surface_blocked_candidate_count": int(
            queue.get("surface_blocked_candidate_count") or 0
        ),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "skipped_count_today": len(skipped_today),
        "pending_count": len(state["pending_entries"]),
        "open_position_count": len(state["open_positions"]),
        "closed_position_count": len(state["closed_positions"]),
        "realized_pnl_to_date": realized,
        "unrealized_pnl": unrealized,
        "surface_summary": _surface_summary(state, queue),
        "state": queue.get("state") or {},
        "parameters": dict(config),
        "data_source": queue.get("data_source") or {},
        "candidates": deepcopy(queue.get("candidates") or []),
        "blocked_candidates": deepcopy(queue.get("blocked_candidates") or []),
        "surface_blocked_candidates": deepcopy(
            queue.get("surface_blocked_candidates") or []
        ),
        "surface_eligibility": deepcopy(
            queue.get("surface_eligibility")
            or _surface_eligibility_payload(config)
        ),
        "ret20_excess_spy_gate": deepcopy(
            queue.get("ret20_excess_spy_gate")
            or _ret20_excess_spy_gate_payload(config)
        ),
        "rank_notional_profile": deepcopy(
            queue.get("rank_notional_profile")
            or _rank_notional_profile_payload(config)
        ),
        "benchmark_momentum_gate": deepcopy(
            queue.get("benchmark_momentum_gate")
            or _blocked_benchmark_momentum_gate("missing_state_surface_queue")
        ),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "closed_positions": deepcopy(state["closed_positions"]),
        "skipped_entries_today": deepcopy(skipped_today),
        "pending_entries": deepcopy(state["pending_entries"]),
        "open_positions": deepcopy(state["open_positions"]),
        "forward_paper_gate": gate,
        "tail_diagnostics": deepcopy(gate.get("tail_diagnostics") or {}),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed = [row for row in closed_positions if isinstance(row, dict)]
    closed_count = len(closed)
    wins = sum(1 for row in closed if _money(row.get("pnl")) > 0)
    win_rate = round(wins / closed_count, 4) if closed_count else None
    realized = round(sum(_money(row.get("pnl")) for row in closed), 2)
    min_closed = int(config["forward_gate_min_closed_trades"])
    tail_diagnostics = build_state_surface_forward_tail_diagnostics(closed, config)
    tail_failures = [
        reason
        for reason in (tail_diagnostics.get("gate_report") or {}).get("hard_failures", [])
        if reason != "insufficient_sample"
    ]
    checks = {
        "min_closed_trades": closed_count >= min_closed,
        "min_win_rate": win_rate is not None and win_rate >= float(config["forward_gate_min_win_rate"]),
        "positive_net_pnl": realized > 0,
        "tail_gate": closed_count < min_closed or not tail_failures,
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": closed_count,
            "realized_pnl": realized,
            "win_rate": win_rate,
        },
        "tail_diagnostics": tail_diagnostics,
        "trade_enabled_after_gate": False,
    }


def build_state_surface_forward_tail_diagnostics(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return read-only tail diagnostics for forward paper sleeve promotion."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    closed = [row for row in closed_positions if isinstance(row, dict)]
    pnl_values = [_money(row.get("pnl")) for row in closed]
    wins = [value for value in pnl_values if value > 0]
    losses = [value for value in pnl_values if value <= 0]
    total_trades = len(pnl_values)
    win_rate = round(len(wins) / total_trades, 4) if total_trades else None
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    expected_value = win_rate * avg_win + (1.0 - win_rate) * avg_loss if win_rate is not None else 0.0
    metrics = {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "total_pnl": round(sum(pnl_values), 2),
        "expected_value_usd": round(expected_value, 2),
        "pnl_skewness": _skew(pnl_values),
        "pnl_excess_kurtosis": _excess_kurtosis(pnl_values),
        "pnl_tail_ratio": _tail_ratio(pnl_values),
        "pnl_top_5_contribution_pct": _top5_contribution(pnl_values),
        "pnl_hhi_concentration": _hhi_concentration(pnl_values),
    }
    thresholds = GateThresholds(
        min_trades_for_promotion=int(cfg["forward_gate_min_closed_trades"]),
        max_top_5_contribution_pct=float(cfg["forward_gate_max_top_5_contribution_pct"]),
        max_hhi_concentration=float(cfg["forward_gate_max_hhi_concentration"]),
    )
    return {
        "schema_version": 1,
        "read_only": True,
        "scope": "state_surface_forward_paper_closed_positions",
        "metrics_for_gates": metrics,
        "gate_report": evaluate_metrics(
            metrics,
            thresholds=thresholds,
            prefer_r_multiple=False,
        ),
        "notes": [
            "True R-multiple is unavailable for this default-off paper sleeve; PnL distribution is used for forward promotion diagnostics.",
            "This diagnostics block does not alter orders, candidates, rank, notional, or paper fills.",
        ],
    }


def _sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return variance ** 0.5


def _skew(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    mean = sum(values) / len(values)
    std = _sample_std(values)
    if not std:
        return None
    return round(sum(((value - mean) / std) ** 3 for value in values) / len(values), 4)


def _excess_kurtosis(values: list[float]) -> float | None:
    if len(values) < 4:
        return None
    mean = sum(values) / len(values)
    std = _sample_std(values)
    if not std:
        return None
    return round(sum(((value - mean) / std) ** 4 for value in values) / len(values) - 3.0, 4)


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def _tail_ratio(values: list[float]) -> float | None:
    if len(values) < 5:
        return None
    ordered = sorted(values)
    p05 = _percentile(ordered, 0.05)
    p95 = _percentile(ordered, 0.95)
    if p05 is None or p95 is None or p05 >= 0:
        return None
    return round(abs(p95) / abs(p05), 4)


def _top5_contribution(values: list[float]) -> float | None:
    positives = sorted([value for value in values if value > 0], reverse=True)
    total = sum(positives)
    if total <= 0:
        return None
    return round(sum(positives[:5]) / total, 4)


def _hhi_concentration(values: list[float]) -> float | None:
    positives = [value for value in values if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return round(sum((value / total) ** 2 for value in positives), 4)


def _surface_summary(state: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, dict[str, Any]] = {}
    for bucket, rows in (
        ("candidate_count", queue.get("candidates") or []),
        ("pending_count", state.get("pending_entries") or []),
        ("open_position_count", state.get("open_positions") or []),
        ("closed_position_count", state.get("closed_positions") or []),
    ):
        for row in rows:
            surface = str(row.get("surface") or (row.get("candidate") or {}).get("surface") or "unknown")
            entry = summary.setdefault(
                surface,
                {
                    "candidate_count": 0,
                    "pending_count": 0,
                    "open_position_count": 0,
                    "closed_position_count": 0,
                    "realized_pnl": 0.0,
                },
            )
            entry[bucket] += 1
            if bucket == "closed_position_count":
                entry["realized_pnl"] = round(entry["realized_pnl"] + _money(row.get("pnl")), 2)
    return summary


def _pending_sort_key(entry: dict[str, Any]) -> tuple[str, int, float, str]:
    return (
        str(entry.get("created_asof") or ""),
        int(entry.get("rank") or 99),
        -float(entry.get("score") or 0.0),
        str(entry.get("ticker") or ""),
    )


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, float, str]:
    return (
        int(candidate.get("rank") or 99),
        -float(candidate.get("score") or 0.0),
        str(candidate.get("ticker") or ""),
    )


def _existing_decision_ids(state: dict[str, Any]) -> set[str]:
    ids = set()
    for bucket in ("pending_entries", "open_positions", "closed_positions", "skipped_entries"):
        ids.update(str(item.get("decision_id")) for item in state.get(bucket, []) if item.get("decision_id"))
    return ids


def _mark_unrealized(
    position: dict[str, Any],
    current_price: float,
    round_trip_cost_pct: float,
) -> None:
    entry = float(position["entry_price"])
    notional = float(position["notional"])
    gross_return = current_price / entry - 1.0
    position["unrealized_return_pct"] = round(gross_return * 100.0, 6)
    position["unrealized_pnl"] = round(notional * gross_return, 2)
    position["net_pnl_if_closed_now"] = round(notional * (gross_return - round_trip_cost_pct), 2)


def _close_position(
    position: dict[str, Any],
    exit_price: float,
    exit_date: str,
    round_trip_cost_pct: float,
) -> dict[str, Any]:
    entry = float(position["entry_price"])
    notional = float(position["notional"])
    gross_return = exit_price / entry - 1.0
    net_return = gross_return - round_trip_cost_pct
    closed = dict(position)
    closed.update(
        {
            "paper_status": "closed",
            "exit_date": exit_date,
            "exit_price": exit_price,
            "gross_return_pct": round(gross_return * 100.0, 6),
            "net_return_pct": round(net_return * 100.0, 6),
            "pnl": round(notional * net_return, 2),
            "trade_enabled": False,
        }
    )
    return closed


def _date10(value: Any) -> str:
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except Exception:
            pass
    return str(value or "")[:10]


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _round(value: Any, digits: int = 4) -> Any:
    parsed = _float_or_none(value)
    return round(parsed, digits) if parsed is not None else None


def _money(value: Any) -> float:
    parsed = _float_or_none(value)
    return round(parsed or 0.0, 2)


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "replay_only": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "scope": "default_off_state_surface_satellite_paper_attribution",
    }
