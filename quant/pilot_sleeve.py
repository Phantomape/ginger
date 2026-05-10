"""Shared real-money pilot sleeve policy for universe expansion candidates.

The pilot sleeve is not a core universe promotion. It lets approved pilot
tickers run through the same signal, enrichment, filtering, and sizing chain as
core candidates, then applies point-in-time sleeve caps before any trade
recommendation is exposed.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from candidate_competition_logger import append_decision_snapshot
from universe_manager import (
    DEFAULT_EVENTS_PATH,
    DEFAULT_REGISTRY_PATH,
    eligible_tickers_as_of,
    load_registry,
    records_as_of,
    registry_hash,
)


AI_INFRA_AGGRESSIVE_SLEEVE_NAME = "AI_INFRA_AGGRESSIVE"
LEGACY_AI_INFRA_PILOT_SLEEVE_NAME = "AI_INFRA_PILOT"
CONSUMER_PLATFORM_SLEEVE_NAME = "CONSUMER_PLATFORM_PILOT"

# Backward-compatible import name used by older tests and replay records. New
# snapshots use the explicit aggressive AI infrastructure sleeve.
PILOT_SLEEVE_NAME = AI_INFRA_AGGRESSIVE_SLEEVE_NAME
PILOT_TRADEABLE_STATUSES = {"pilot", "limited_production"}
MAX_CONCURRENT_PILOT_POSITIONS = 1

AI_INFRA_THEME_SEGMENTS = {
    "ai_semiconductor_turnaround": "compute_memory_semis",
    "ai_storage_semis": "compute_memory_semis",
    "ai_memory_storage": "compute_memory_semis",
    "ai_optical_connectivity": "optical_connectivity",
    "ai_power_energy": "power_datacenter_infra",
    "ai_datacenter_infra": "power_datacenter_infra",
    "ai_gpu_cloud": "specialist_compute_cloud",
    "btc_miner_hpc": "specialist_compute_cloud",
}

SLEEVE_POLICIES = {
    AI_INFRA_AGGRESSIVE_SLEEVE_NAME: {
        "base_max_concurrent_positions": 1,
        "bull_max_concurrent_positions": 2,
        "sleeve_max_capital_pct": 0.18,
        "sleeve_max_risk_pct": 0.10,
        "segment_limit_per_sleeve": 1,
        "selection_policy": (
            "trade_quality_score_then_confidence_then_risk_reward_with_segment_cap"
        ),
    },
    CONSUMER_PLATFORM_SLEEVE_NAME: {
        "base_max_concurrent_positions": 1,
        "bull_max_concurrent_positions": 1,
        "sleeve_max_capital_pct": 0.10,
        "sleeve_max_risk_pct": 0.06,
        "segment_limit_per_sleeve": None,
        "selection_policy": "trade_quality_score_then_confidence_then_risk_reward",
    },
}


def _as_float(value) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _theme_segment(record: dict | None) -> str:
    record = record or {}
    explicit = record.get("theme_segment") or record.get("segment")
    if explicit:
        return str(explicit)
    theme = str(record.get("theme") or "").lower()
    return AI_INFRA_THEME_SEGMENTS.get(theme, theme or "unknown")


def pilot_sleeve_name_for_record(record: dict | None) -> str:
    record = record or {}
    theme = str(record.get("theme") or "").lower()
    explicit = record.get("pilot_sleeve") or record.get("sleeve")
    if explicit == LEGACY_AI_INFRA_PILOT_SLEEVE_NAME:
        return AI_INFRA_AGGRESSIVE_SLEEVE_NAME
    if explicit:
        return str(explicit)
    if theme == "consumer_digital_platform":
        return CONSUMER_PLATFORM_SLEEVE_NAME
    if theme.startswith("ai_") or theme == "btc_miner_hpc":
        return AI_INFRA_AGGRESSIVE_SLEEVE_NAME
    return AI_INFRA_AGGRESSIVE_SLEEVE_NAME


def _sleeve_policy(sleeve_name: str | None) -> dict:
    return SLEEVE_POLICIES.get(
        str(sleeve_name or ""),
        SLEEVE_POLICIES[CONSUMER_PLATFORM_SLEEVE_NAME],
    )


def _relative_qqq_strength_positive(market_context: dict | None) -> bool:
    context = market_context or {}
    candidates = (
        ("qqq_minus_spy_ret20", None),
        ("qqq_20d_return", "spy_20d_return"),
        ("qqq_10d_return", "spy_10d_return"),
        ("qqq_pct_from_ma", "spy_pct_from_ma"),
    )
    for qqq_key, spy_key in candidates:
        qqq_value = context.get(qqq_key)
        if qqq_value is None:
            continue
        if spy_key is None:
            return _as_float(qqq_value) > 0
        spy_value = context.get(spy_key)
        if spy_value is None:
            continue
        return _as_float(qqq_value) > _as_float(spy_value)
    return False


def ai_infra_bull_booster_active(market_context: dict | None) -> bool:
    context = market_context or {}
    return (
        str(context.get("market_regime") or "").upper() == "BULL"
        and _relative_qqq_strength_positive(context)
    )


def max_concurrent_for_sleeve(
    sleeve_name: str,
    market_context: dict | None = None,
) -> tuple[int, bool]:
    policy = _sleeve_policy(sleeve_name)
    bull_booster = (
        sleeve_name == AI_INFRA_AGGRESSIVE_SLEEVE_NAME
        and ai_infra_bull_booster_active(market_context)
    )
    key = "bull_max_concurrent_positions" if bull_booster else "base_max_concurrent_positions"
    return int(policy.get(key) or MAX_CONCURRENT_PILOT_POSITIONS), bull_booster


def _pilot_selection_priority(
    signal: dict,
    original_index: int,
) -> tuple[float, float, float, int, int]:
    sizing = signal.get("sizing") or {}
    return (
        _as_float(signal.get("trade_quality_score")),
        _as_float(signal.get("confidence_score")),
        _as_float(signal.get("risk_reward_ratio")),
        int(sizing.get("shares_to_buy") or 0),
        -original_index,
    )


def _signal_sleeve_name(signal: dict | None) -> str:
    sleeve = (signal or {}).get("pilot_sleeve") or {}
    return sleeve.get("name") or PILOT_SLEEVE_NAME


def _same_sleeve_alternative_counterfactual(
    pilot: dict,
    alternative_signals: list[dict],
) -> dict | None:
    pilot_ticker = pilot.get("ticker")
    pilot_sleeve = _signal_sleeve_name(pilot)
    ranked = []
    for original_index, signal in enumerate(alternative_signals or []):
        if signal.get("ticker") == pilot_ticker:
            continue
        if _signal_sleeve_name(signal) != pilot_sleeve:
            continue
        sizing = signal.get("sizing") or {}
        if _as_float(sizing.get("shares_to_buy")) <= 0:
            continue
        ranked.append((_pilot_selection_priority(signal, original_index), signal))

    if not ranked:
        return None

    ranked.sort(key=lambda item: item[0], reverse=True)
    signal = ranked[0][1]
    sizing = signal.get("sizing") or {}
    sleeve = signal.get("pilot_sleeve") or {}
    return {
        "type": "same_sleeve_alternative_candidate",
        "ticker": signal.get("ticker"),
        "shadow_weight": 0.0,
        "evaluation_only": True,
        "sleeve": sleeve.get("name") or pilot_sleeve,
        "segment": sleeve.get("segment"),
        "slot_decision": sleeve.get("slot_decision"),
        "strategy": signal.get("strategy"),
        "trade_quality_score": signal.get("trade_quality_score"),
        "confidence_score": signal.get("confidence_score"),
        "risk_reward_ratio": signal.get("risk_reward_ratio"),
        "entry_price": signal.get("entry_price"),
        "stop_price": signal.get("stop_price"),
        "target_price": signal.get("target_price"),
        "shares_to_buy": sizing.get("shares_to_buy"),
        "planned_risk": sizing.get("risk_amount_usd"),
    }


def file_hash(path: Path | str) -> str | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def pilot_records_as_of(
    as_of,
    *,
    sleeve: str | None = None,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
) -> dict[str, dict]:
    """Return pilot/limited-production records allowed to trade as of `as_of`."""
    eligible = set(
        eligible_tickers_as_of(
            as_of,
            statuses=PILOT_TRADEABLE_STATUSES,
            require_trade_allowed=True,
            registry_path=registry_path,
            events_path=events_path,
        )
    )
    all_records = records_as_of(
        as_of,
        registry_path=registry_path,
        events_path=events_path,
        prefer_events=True,
    )
    records = {}
    for ticker in sorted(eligible):
        record = all_records.get(ticker)
        if not record:
            continue
        max_risk_scalar = float(record.get("max_risk_scalar") or 0.0)
        if max_risk_scalar <= 0:
            continue
        enriched = deepcopy(record)
        enriched["pilot_sleeve"] = pilot_sleeve_name_for_record(enriched)
        enriched["theme_segment"] = _theme_segment(enriched)
        if sleeve and enriched["pilot_sleeve"] != sleeve:
            continue
        records[ticker] = enriched
    return records


def pilot_tickers_as_of(as_of, **kwargs) -> list[str]:
    """Return trade-enabled pilot tickers as of `as_of`."""
    return sorted(pilot_records_as_of(as_of, **kwargs))


def pilot_governance_metadata(
    *,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
) -> dict:
    registry = load_registry(registry_path)
    return {
        "protocol_version": registry.get("protocol_version"),
        "schema_version": registry.get("schema_version"),
        "registry_hash": registry_hash(registry),
        "event_ledger_hash": file_hash(events_path),
        "sleeve_policies": deepcopy(SLEEVE_POLICIES),
    }


def mark_pilot_signals(
    signals: list[dict],
    pilot_records: dict[str, dict],
    *,
    metadata: dict | None = None,
) -> list[dict]:
    """Attach sleeve metadata without changing signal ordering or core fields."""
    metadata = metadata or {}
    marked = []
    for signal in signals or []:
        ticker = signal.get("ticker")
        record = pilot_records.get(ticker)
        if not record:
            continue
        out = deepcopy(signal)
        sleeve_name = pilot_sleeve_name_for_record(record)
        segment = _theme_segment(record)
        policy = _sleeve_policy(sleeve_name)
        out["universe_status"] = record.get("status")
        out["pilot_trade_enabled"] = True
        out["pilot_sleeve"] = {
            "name": sleeve_name,
            "theme": record.get("theme"),
            "segment": segment,
            "history_class": record.get("history_class"),
            "liquidity_tier": record.get("liquidity_tier"),
            "event_guard_profile": record.get("event_guard_profile"),
            "requires_event_guard": bool(record.get("requires_event_guard")),
            "max_capital_scalar": float(record.get("max_capital_scalar") or 0.0),
            "max_risk_scalar": float(record.get("max_risk_scalar") or 0.0),
            "sleeve_max_capital_pct": policy.get("sleeve_max_capital_pct"),
            "sleeve_max_risk_pct": policy.get("sleeve_max_risk_pct"),
            "competes_for_core_slots": bool(record.get("competes_for_core_slots")),
            "rule_version": record.get("rule_version"),
            "registry_hash": metadata.get("registry_hash"),
            "event_ledger_hash": metadata.get("event_ledger_hash"),
        }
        marked.append(out)
    return marked


def apply_pilot_sizing_policy(
    signals: list[dict],
    pilot_records: dict[str, dict],
) -> list[dict]:
    """Apply registry risk/capital scalars to already-sized pilot signals."""
    scaled = []
    for signal in signals or []:
        ticker = signal.get("ticker")
        record = pilot_records.get(ticker) or {}
        out = deepcopy(signal)
        sizing = deepcopy(out.get("sizing") or {})
        if not sizing:
            scaled.append(out)
            continue

        original_sizing = deepcopy(sizing)
        sleeve_name = pilot_sleeve_name_for_record(record)
        policy = _sleeve_policy(sleeve_name)
        max_capital_scalar = float(record.get("max_capital_scalar") or 0.0)
        max_risk_scalar = float(record.get("max_risk_scalar") or 0.0)
        sleeve_scalar = max(0.0, min(max_capital_scalar, max_risk_scalar))
        original_shares = int(sizing.get("shares_to_buy") or 0)
        scaled_shares = int(original_shares * sleeve_scalar)
        scale = (scaled_shares / original_shares) if original_shares > 0 else 0.0

        sizing["pilot_original_sizing"] = original_sizing
        sizing["pilot_sleeve_scalar_applied"] = round(sleeve_scalar, 4)
        sizing["pilot_max_capital_scalar"] = max_capital_scalar
        sizing["pilot_max_risk_scalar"] = max_risk_scalar
        sizing["pilot_sleeve_name"] = sleeve_name
        sizing["pilot_sleeve_max_capital_pct"] = policy.get("sleeve_max_capital_pct")
        sizing["pilot_sleeve_max_risk_pct"] = policy.get("sleeve_max_risk_pct")
        sizing["shares_to_buy"] = scaled_shares
        for key in (
            "risk_pct",
            "risk_amount_usd",
            "position_value_usd",
            "position_pct_of_portfolio",
        ):
            if isinstance(sizing.get(key), (int, float)):
                sizing[key] = round(float(sizing[key]) * scale, 6)
        sizing["pilot_sleeve_tradeable"] = scaled_shares > 0
        if scaled_shares <= 0:
            sizing["pilot_sleeve_block_reason"] = "scaled_shares_zero"

        out["sizing"] = sizing
        scaled.append(out)
    return scaled


def _positive_positions(open_positions: dict | None) -> list[dict]:
    return [
        pos
        for pos in (open_positions or {}).get("positions", [])
        if pos.get("ticker") and (pos.get("shares") or 0) > 0
    ]


def _position_capital_pct(pos: dict, open_positions: dict | None) -> float:
    explicit = _as_float(pos.get("position_pct_of_portfolio"))
    if explicit > 0:
        return explicit
    portfolio_value = _as_float((open_positions or {}).get("portfolio_value_usd"))
    shares = _as_float(pos.get("shares"))
    price = _as_float(pos.get("current_price") or pos.get("avg_cost"))
    if portfolio_value > 0 and shares > 0 and price > 0:
        return (shares * price) / portfolio_value
    return 0.0


def _position_risk_pct(pos: dict) -> float:
    for key in ("actual_risk_pct", "risk_pct", "initial_risk_pct"):
        explicit = _as_float(pos.get(key))
        if explicit > 0:
            return explicit
    return 0.0


def select_pilot_entry_candidates(
    signals: list[dict],
    pilot_records: dict[str, dict],
    *,
    open_positions: dict | None = None,
    max_concurrent: int = MAX_CONCURRENT_PILOT_POSITIONS,
    market_context: dict | None = None,
) -> tuple[list[dict], dict]:
    """Keep the highest-ranked tradeable pilot signals within each sleeve."""
    input_signals = list(signals or [])
    enriched_records = {}
    for ticker, record in (pilot_records or {}).items():
        enriched = deepcopy(record or {})
        enriched.setdefault("ticker", ticker)
        enriched["pilot_sleeve"] = pilot_sleeve_name_for_record(enriched)
        enriched["theme_segment"] = _theme_segment(enriched)
        enriched_records[ticker] = enriched

    signals_by_sleeve: dict[str, list[tuple[int, dict]]] = {}
    for idx, sig in enumerate(input_signals):
        ticker = sig.get("ticker")
        record = enriched_records.get(ticker) or {}
        sleeve_name = (
            ((sig.get("pilot_sleeve") or {}).get("name"))
            or pilot_sleeve_name_for_record(record)
        )
        signals_by_sleeve.setdefault(sleeve_name, []).append((idx, sig))

    all_active_positions = _positive_positions(open_positions)
    selected: list[dict] = []
    dropped: list[dict] = []
    by_sleeve = {}

    for sleeve_name in sorted(signals_by_sleeve):
        policy = _sleeve_policy(sleeve_name)
        sleeve_max_concurrent, bull_booster = max_concurrent_for_sleeve(
            sleeve_name,
            market_context,
        )
        if sleeve_name not in SLEEVE_POLICIES:
            sleeve_max_concurrent = int(max_concurrent)

        sleeve_tickers = {
            ticker
            for ticker, record in enriched_records.items()
            if record.get("pilot_sleeve") == sleeve_name
        }
        active_positions = [
            pos
            for pos in all_active_positions
            if pos.get("ticker") in sleeve_tickers
        ]
        active_segments = {
            enriched_records.get(pos.get("ticker"), {}).get("theme_segment")
            for pos in active_positions
            if enriched_records.get(pos.get("ticker"), {}).get("theme_segment")
        }
        available_slots = max(
            0,
            int(sleeve_max_concurrent) - len(active_positions),
        )
        ranked_tradeable = [
            (sig, _pilot_selection_priority(sig, idx), idx)
            for idx, sig in signals_by_sleeve[sleeve_name]
            if (sig.get("sizing") or {}).get("shares_to_buy", 0) > 0
        ]
        ranked_tradeable.sort(key=lambda item: item[1], reverse=True)

        sleeve_selected = []
        sleeve_dropped = []
        processed_original_ids = set()
        used_segments = set(active_segments)
        active_capital_pct = sum(
            _position_capital_pct(pos, open_positions)
            for pos in active_positions
        )
        selected_capital_pct = active_capital_pct
        active_risk_pct = sum(_position_risk_pct(pos) for pos in active_positions)
        selected_risk_pct = active_risk_pct
        sleeve_capital_pct = policy.get("sleeve_max_capital_pct")
        sleeve_risk_pct = policy.get("sleeve_max_risk_pct")
        segment_limit = policy.get("segment_limit_per_sleeve")

        for sig, _priority, _idx in ranked_tradeable:
            ticker = sig.get("ticker")
            record = enriched_records.get(ticker) or {}
            segment = (
                ((sig.get("pilot_sleeve") or {}).get("segment"))
                or record.get("theme_segment")
                or _theme_segment(record)
            )
            sizing = sig.get("sizing") or {}
            signal_capital_pct = _as_float(sizing.get("position_pct_of_portfolio"))
            signal_risk_pct = _as_float(sizing.get("risk_pct"))

            drop_reason = None
            if len(sleeve_selected) >= available_slots:
                drop_reason = "sleeve_slot_limit"
            elif segment_limit and segment in used_segments:
                drop_reason = "sleeve_segment_limit"
            elif (
                isinstance(sleeve_capital_pct, (int, float))
                and sleeve_capital_pct > 0
                and signal_capital_pct > 0
                and selected_capital_pct + signal_capital_pct > sleeve_capital_pct + 1e-9
            ):
                drop_reason = "sleeve_capital_limit"
            elif (
                isinstance(sleeve_risk_pct, (int, float))
                and sleeve_risk_pct > 0
                and signal_risk_pct > 0
                and selected_risk_pct + signal_risk_pct > sleeve_risk_pct + 1e-9
            ):
                drop_reason = "sleeve_risk_limit"

            if drop_reason:
                out = deepcopy(sig)
                out.setdefault("pilot_sleeve", {})["slot_decision"] = drop_reason
                sleeve_dropped.append(out)
                processed_original_ids.add(id(sig))
                continue

            out = deepcopy(sig)
            out.setdefault("pilot_sleeve", {})["slot_decision"] = "selected"
            out.setdefault("pilot_sleeve", {})["bull_booster_active"] = bull_booster
            sleeve_selected.append(out)
            processed_original_ids.add(id(sig))
            if segment:
                used_segments.add(segment)
            selected_capital_pct += signal_capital_pct
            selected_risk_pct += signal_risk_pct

        for _idx, sig in signals_by_sleeve[sleeve_name]:
            if id(sig) in processed_original_ids:
                continue
            out = deepcopy(sig)
            out.setdefault("pilot_sleeve", {})["slot_decision"] = "not_tradeable"
            sleeve_dropped.append(out)

        selected.extend(sleeve_selected)
        dropped.extend(sleeve_dropped)
        by_sleeve[sleeve_name] = {
            "sleeve": sleeve_name,
            "selection_policy": policy.get("selection_policy"),
            "base_max_concurrent_positions": policy.get("base_max_concurrent_positions"),
            "max_concurrent_positions": sleeve_max_concurrent,
            "bull_booster_active": bull_booster,
            "active_pilot_positions": [pos.get("ticker") for pos in active_positions],
            "active_segments": sorted(active_segments),
            "available_pilot_slots": available_slots,
            "sleeve_max_capital_pct": sleeve_capital_pct,
            "sleeve_max_risk_pct": sleeve_risk_pct,
            "active_capital_pct": round(active_capital_pct, 6),
            "selected_capital_pct": round(selected_capital_pct, 6),
            "active_risk_pct": round(active_risk_pct, 6),
            "selected_risk_pct": round(selected_risk_pct, 6),
            "signals_before_pilot_slotting": len(signals_by_sleeve[sleeve_name]),
            "tradeable_pilot_signals": len(ranked_tradeable),
            "signals_after_pilot_slotting": len(sleeve_selected),
            "pilot_slot_sliced_signals": sleeve_dropped,
        }

    overall_selection_policy = "per_sleeve_policy"
    if len(by_sleeve) == 1:
        only_sleeve = next(iter(by_sleeve.values()))
        overall_selection_policy = only_sleeve.get("selection_policy")

    audit = {
        "sleeve": "multi_pilot_sleeve",
        "selection_policy": overall_selection_policy,
        "max_concurrent_positions": max_concurrent,
        "active_pilot_positions": sorted(
            {
                ticker
                for sleeve_audit in by_sleeve.values()
                for ticker in sleeve_audit["active_pilot_positions"]
            }
        ),
        "available_pilot_slots": sum(
            sleeve_audit["available_pilot_slots"]
            for sleeve_audit in by_sleeve.values()
        ),
        "signals_before_pilot_slotting": len(input_signals),
        "tradeable_pilot_signals": sum(
            sleeve_audit["tradeable_pilot_signals"]
            for sleeve_audit in by_sleeve.values()
        ),
        "signals_after_pilot_slotting": len(selected),
        "pilot_slot_sliced_signals": dropped,
        "by_sleeve": by_sleeve,
    }
    return selected, audit


def build_counterfactual_snapshots(
    pilot_signals: list[dict],
    *,
    core_signals: list[dict] | None = None,
    pilot_alternative_signals: list[dict] | None = None,
    as_of: str | None = None,
    market_context: dict | None = None,
    portfolio_heat: dict | None = None,
    metadata: dict | None = None,
) -> list[dict]:
    """Freeze pre-trade counterfactuals for pilot entries."""
    metadata = metadata or {}
    market_context = market_context or {}
    core_signals = list(core_signals or [])
    pilot_alternative_signals = list(pilot_alternative_signals or [])
    timestamp = datetime.now(timezone.utc).isoformat()
    as_of_str = str(as_of or datetime.now(timezone.utc).date().isoformat())

    ranking_snapshot = []
    for status, signals in (
        ("pilot", pilot_signals),
        ("pilot_sliced", pilot_alternative_signals),
        ("core", core_signals),
    ):
        for rank, signal in enumerate(signals or [], start=1):
            sizing = signal.get("sizing") or {}
            sleeve = signal.get("pilot_sleeve") or {}
            ranking_snapshot.append(
                {
                    "rank": rank,
                    "status": status,
                    "ticker": signal.get("ticker"),
                    "strategy": signal.get("strategy"),
                    "confidence_score": signal.get("confidence_score"),
                    "trade_quality_score": signal.get("trade_quality_score"),
                    "sector": signal.get("sector"),
                    "entry_price": signal.get("entry_price"),
                    "stop_price": signal.get("stop_price"),
                    "target_price": signal.get("target_price"),
                    "shares_to_buy": sizing.get("shares_to_buy"),
                    "risk_amount_usd": sizing.get("risk_amount_usd"),
                    "position_value_usd": sizing.get("position_value_usd"),
                    "pilot_sleeve": sleeve.get("name"),
                    "pilot_segment": sleeve.get("segment"),
                    "slot_decision": sleeve.get("slot_decision"),
                }
            )
    if not ranking_snapshot:
        return []

    snapshots = []
    for idx, pilot in enumerate(pilot_signals or [], start=1):
        pilot_ticker = pilot.get("ticker")
        pilot_sleeve = (pilot.get("pilot_sleeve") or {}).get("name") or PILOT_SLEEVE_NAME
        displaced = next(
            (
                signal
                for signal in core_signals
                if signal.get("ticker") != pilot_ticker
                and (signal.get("sizing") or {}).get("shares_to_buy", 0) > 0
            ),
            None,
        )
        if displaced:
            displaced_sizing = displaced.get("sizing") or {}
            counterfactuals = [
                {
                    "type": "primary_displaced_candidate",
                    "ticker": displaced.get("ticker"),
                    "shadow_weight": 0.5,
                    "strategy": displaced.get("strategy"),
                    "trade_quality_score": displaced.get("trade_quality_score"),
                    "entry_price": displaced.get("entry_price"),
                    "stop_price": displaced.get("stop_price"),
                    "target_price": displaced.get("target_price"),
                    "shares_to_buy": displaced_sizing.get("shares_to_buy"),
                    "planned_risk": displaced_sizing.get("risk_amount_usd"),
                },
                {
                    "type": "cash_baseline",
                    "ticker": "CASH",
                    "shadow_weight": 0.5,
                },
            ]
        else:
            counterfactuals = [
                {
                    "type": "cash_baseline",
                    "ticker": "CASH",
                    "shadow_weight": 1.0,
                }
            ]

        same_sleeve_alternative = _same_sleeve_alternative_counterfactual(
            pilot,
            pilot_alternative_signals,
        )
        if same_sleeve_alternative:
            counterfactuals.append(same_sleeve_alternative)

        snapshots.append(
            {
                "decision_id": (
                    f"{as_of_str}-{pilot_sleeve}-"
                    f"{pilot_ticker}-{pilot.get('strategy')}-{idx}"
                ),
                "timestamp": timestamp,
                "sleeve": pilot_sleeve,
                "pilot_ticker": pilot_ticker,
                "action": "pilot_entry_candidate",
                "protocol_version": metadata.get("protocol_version"),
                "registry_hash": metadata.get("registry_hash"),
                "event_ledger_hash": metadata.get("event_ledger_hash"),
                "ranking_snapshot": ranking_snapshot,
                "counterfactuals": counterfactuals,
                "risk_snapshot": {
                    "market_regime": market_context.get("market_regime"),
                    "spy_pct_from_ma": market_context.get("spy_pct_from_ma"),
                    "qqq_pct_from_ma": market_context.get("qqq_pct_from_ma"),
                    "portfolio_heat_pct": (
                        portfolio_heat or {}
                    ).get("portfolio_heat_pct"),
                    "pilot_sizing": pilot.get("sizing"),
                    "pilot_sleeve": pilot.get("pilot_sleeve"),
                },
            }
        )
    return snapshots


def append_pilot_decision_snapshots(snapshots: list[dict]) -> list[str]:
    """Persist pre-trade snapshots and return their hashes."""
    hashes = []
    for snapshot in snapshots or []:
        hashes.append(append_decision_snapshot(snapshot))
    return hashes


def _signal_summary(signal: dict) -> dict:
    sizing = signal.get("sizing") or {}
    sleeve = signal.get("pilot_sleeve") or {}
    return {
        "ticker": signal.get("ticker"),
        "strategy": signal.get("strategy"),
        "segment": sleeve.get("segment"),
        "slot_decision": sleeve.get("slot_decision"),
        "trade_quality_score": signal.get("trade_quality_score"),
        "confidence_score": signal.get("confidence_score"),
        "risk_reward_ratio": signal.get("risk_reward_ratio"),
        "shares_to_buy": sizing.get("shares_to_buy"),
        "risk_pct": sizing.get("risk_pct"),
        "position_pct_of_portfolio": sizing.get("position_pct_of_portfolio"),
    }


def build_ai_infra_aggressive_attribution(
    *,
    pilot_signals: list[dict],
    pilot_entry_execution_plan: dict | None,
    pilot_attribution: dict | None = None,
) -> dict:
    """Build the daily AI infra sleeve surface requested by the experiment."""
    plan = pilot_entry_execution_plan or {}
    sleeve_plan = (plan.get("by_sleeve") or {}).get(
        AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
        {},
    )
    selected = [
        _signal_summary(signal)
        for signal in (pilot_signals or [])
        if (signal.get("pilot_sleeve") or {}).get("name")
        == AI_INFRA_AGGRESSIVE_SLEEVE_NAME
    ]
    sliced = [
        _signal_summary(signal)
        for signal in (sleeve_plan.get("pilot_slot_sliced_signals") or [])
    ]
    segments = sorted(
        {
            item.get("segment")
            for item in selected + sliced
            if item.get("segment")
        }
    )
    attribution = pilot_attribution or {}
    return {
        "sleeve": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
        "enabled": bool(sleeve_plan or selected or sliced),
        "bull_booster_active": bool(sleeve_plan.get("bull_booster_active")),
        "max_concurrent_positions": sleeve_plan.get("max_concurrent_positions"),
        "sleeve_max_capital_pct": sleeve_plan.get("sleeve_max_capital_pct"),
        "selected": selected,
        "sliced": sliced,
        "segments_observed": segments,
        "cash_relative_pnl": attribution.get("cash_relative_pnl"),
        "core_replacement_value": attribution.get("replacement_value"),
        "same_theme_replacement_value": attribution.get(
            "same_sleeve_replacement_value"
        ),
        "same_theme_replacement_value_status": attribution.get(
            "same_sleeve_replacement_value_status",
            "pending_forward_outcomes",
        ),
        "risk_adjusted_replacement_value_avg": attribution.get(
            "risk_adjusted_replacement_value_avg"
        ),
        "by_ticker": attribution.get("by_ticker", {}),
    }
