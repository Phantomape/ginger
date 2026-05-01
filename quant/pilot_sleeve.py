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


PILOT_SLEEVE_NAME = "AI_INFRA_PILOT"
PILOT_TRADEABLE_STATUSES = {"pilot", "limited_production"}
MAX_CONCURRENT_PILOT_POSITIONS = 1


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
        records[ticker] = record
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
        out["universe_status"] = record.get("status")
        out["pilot_trade_enabled"] = True
        out["pilot_sleeve"] = {
            "name": PILOT_SLEEVE_NAME,
            "theme": record.get("theme"),
            "history_class": record.get("history_class"),
            "liquidity_tier": record.get("liquidity_tier"),
            "event_guard_profile": record.get("event_guard_profile"),
            "requires_event_guard": bool(record.get("requires_event_guard")),
            "max_capital_scalar": float(record.get("max_capital_scalar") or 0.0),
            "max_risk_scalar": float(record.get("max_risk_scalar") or 0.0),
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


def select_pilot_entry_candidates(
    signals: list[dict],
    pilot_records: dict[str, dict],
    *,
    open_positions: dict | None = None,
    max_concurrent: int = MAX_CONCURRENT_PILOT_POSITIONS,
) -> tuple[list[dict], dict]:
    """Keep only the highest-ranked tradeable pilot signals within sleeve slots."""
    input_signals = list(signals or [])
    pilot_tickers = set(pilot_records)
    active_pilot_positions = [
        pos
        for pos in _positive_positions(open_positions)
        if pos.get("ticker") in pilot_tickers
    ]
    available_slots = max(0, int(max_concurrent) - len(active_pilot_positions))
    tradeable = [
        sig
        for sig in input_signals
        if (sig.get("sizing") or {}).get("shares_to_buy", 0) > 0
    ]
    selected = tradeable[:available_slots]
    selected_ids = {id(sig) for sig in selected}
    dropped = [sig for sig in input_signals if id(sig) not in selected_ids]
    audit = {
        "sleeve": PILOT_SLEEVE_NAME,
        "max_concurrent_positions": max_concurrent,
        "active_pilot_positions": [
            pos.get("ticker") for pos in active_pilot_positions
        ],
        "available_pilot_slots": available_slots,
        "signals_before_pilot_slotting": len(input_signals),
        "tradeable_pilot_signals": len(tradeable),
        "signals_after_pilot_slotting": len(selected),
        "pilot_slot_sliced_signals": dropped,
    }
    return selected, audit


def build_counterfactual_snapshots(
    pilot_signals: list[dict],
    *,
    core_signals: list[dict] | None = None,
    as_of: str | None = None,
    market_context: dict | None = None,
    portfolio_heat: dict | None = None,
    metadata: dict | None = None,
) -> list[dict]:
    """Freeze pre-trade counterfactuals for pilot entries."""
    metadata = metadata or {}
    market_context = market_context or {}
    core_signals = list(core_signals or [])
    timestamp = datetime.now(timezone.utc).isoformat()
    as_of_str = str(as_of or datetime.now(timezone.utc).date().isoformat())

    ranking_snapshot = []
    for status, signals in (("pilot", pilot_signals), ("core", core_signals)):
        for rank, signal in enumerate(signals or [], start=1):
            ranking_snapshot.append(
                {
                    "rank": rank,
                    "status": status,
                    "ticker": signal.get("ticker"),
                    "strategy": signal.get("strategy"),
                    "confidence_score": signal.get("confidence_score"),
                    "trade_quality_score": signal.get("trade_quality_score"),
                    "sector": signal.get("sector"),
                    "shares_to_buy": (signal.get("sizing") or {}).get("shares_to_buy"),
                }
            )
    if not ranking_snapshot:
        return []

    snapshots = []
    for idx, pilot in enumerate(pilot_signals or [], start=1):
        pilot_ticker = pilot.get("ticker")
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
            counterfactuals = [
                {
                    "type": "primary_displaced_candidate",
                    "ticker": displaced.get("ticker"),
                    "shadow_weight": 0.5,
                    "strategy": displaced.get("strategy"),
                    "trade_quality_score": displaced.get("trade_quality_score"),
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

        snapshots.append(
            {
                "decision_id": (
                    f"{as_of_str}-{PILOT_SLEEVE_NAME}-"
                    f"{pilot_ticker}-{pilot.get('strategy')}-{idx}"
                ),
                "timestamp": timestamp,
                "sleeve": PILOT_SLEEVE_NAME,
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
