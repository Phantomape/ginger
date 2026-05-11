"""Observe-only governance helpers for the space catalyst theme.

The space catalyst sleeve starts as a shadow universe, not a pilot trade
adapter. It lets the daily system and experiments see a clean, auditable pool
without letting UFO/SpaceX headlines bypass the normal core and pilot gates.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

from pilot_sleeve import (
    SPACE_CATALYST_SHADOW_SLEEVE_NAME,
    SPACE_CATALYST_THEME_SEGMENTS,
)
from universe_manager import (
    DEFAULT_EVENTS_PATH,
    DEFAULT_REGISTRY_PATH,
    records_as_of,
)


SPACE_CATALYST_LLM_EVENT_FIELDS = (
    "uap_attention_spike",
    "spacex_ipo_proxy",
    "government_space_contract",
    "launch_success",
    "launch_failure",
    "dilution_risk",
    "meme_spike",
)

SPACE_CATALYST_PROMOTION_GATES = {
    "mode": "observe_only",
    "minimum_active_signal_days": 30,
    "minimum_closed_decisions": 10,
    "direct_pnl_required": "> 0",
    "replacement_value_required": "> 0",
    "risk_adjusted_replacement_value_required": "> 0",
    "max_single_ticker_positive_contribution": 0.70,
}

SPACE_CATALYST_STOP_RULES = (
    "Do not trade from UAP/disclosure headlines alone.",
    "Do not trade until a separate pilot promotion creates explicit live slots.",
    "Treat offerings, dilution, launch failure, and mission binary risk as veto fields.",
)


def empty_space_catalyst_shadow_snapshot(as_of, reason: str = "not_built") -> dict:
    return {
        "sleeve": SPACE_CATALYST_SHADOW_SLEEVE_NAME,
        "as_of": str(as_of),
        "mode": "observe_only",
        "candidate_count": 0,
        "status_counts": {},
        "segment_counts": {},
        "tickers_by_segment": {},
        "trade_enabled_tickers": [],
        "llm_event_fields": list(SPACE_CATALYST_LLM_EVENT_FIELDS),
        "promotion_gates": deepcopy(SPACE_CATALYST_PROMOTION_GATES),
        "stop_rules": list(SPACE_CATALYST_STOP_RULES),
        "reason": reason,
    }


def is_space_catalyst_record(record: dict | None) -> bool:
    record = record or {}
    sleeve = record.get("pilot_sleeve") or record.get("sleeve")
    theme = str(record.get("theme") or "").lower()
    return (
        sleeve == SPACE_CATALYST_SHADOW_SLEEVE_NAME
        or theme in SPACE_CATALYST_THEME_SEGMENTS
        or theme.startswith("space_")
    )


def space_catalyst_records_as_of(
    as_of,
    *,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
    include_quarantine: bool = True,
) -> dict[str, dict]:
    """Return point-in-time space catalyst records, including research rows."""
    records = records_as_of(
        as_of,
        registry_path=registry_path,
        events_path=events_path,
        prefer_events=True,
    )
    out = {}
    for ticker, record in sorted(records.items()):
        if not is_space_catalyst_record(record):
            continue
        if record.get("status") == "quarantine" and not include_quarantine:
            continue
        enriched = deepcopy(record)
        enriched.setdefault("ticker", ticker)
        enriched["pilot_sleeve"] = SPACE_CATALYST_SHADOW_SLEEVE_NAME
        enriched.setdefault(
            "theme_segment",
            SPACE_CATALYST_THEME_SEGMENTS.get(
                str(enriched.get("theme") or "").lower(),
                str(enriched.get("theme") or "unknown"),
            ),
        )
        out[ticker] = enriched
    return out


def build_space_catalyst_shadow_snapshot(
    as_of,
    *,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
) -> dict:
    """Build a deterministic observe-only snapshot for daily reporting/logs."""
    records = space_catalyst_records_as_of(
        as_of,
        registry_path=registry_path,
        events_path=events_path,
    )
    status_counts = Counter(record.get("status") for record in records.values())
    segment_counts = Counter(record.get("theme_segment") for record in records.values())
    tickers_by_segment = defaultdict(list)
    trade_enabled = []
    for ticker, record in records.items():
        tickers_by_segment[record.get("theme_segment")].append(ticker)
        if record.get("first_trade_allowed_as_of") and (
            float(record.get("max_capital_scalar") or 0.0) > 0
            or float(record.get("max_risk_scalar") or 0.0) > 0
        ):
            trade_enabled.append(ticker)

    return {
        "sleeve": SPACE_CATALYST_SHADOW_SLEEVE_NAME,
        "as_of": str(as_of),
        "mode": "observe_only",
        "candidate_count": len(records),
        "status_counts": dict(sorted(status_counts.items(), key=lambda item: str(item[0]))),
        "segment_counts": dict(sorted(segment_counts.items(), key=lambda item: str(item[0]))),
        "tickers_by_segment": {
            segment: sorted(tickers)
            for segment, tickers in sorted(
                tickers_by_segment.items(),
                key=lambda item: str(item[0]),
            )
        },
        "trade_enabled_tickers": sorted(trade_enabled),
        "llm_event_fields": list(SPACE_CATALYST_LLM_EVENT_FIELDS),
        "promotion_gates": deepcopy(SPACE_CATALYST_PROMOTION_GATES),
        "stop_rules": list(SPACE_CATALYST_STOP_RULES),
    }
