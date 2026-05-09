"""Position entry-intent metadata helpers.

The production add-on path needs to know the intended entry size, not just the
current broker share count.  Without that metadata, a deliberately conservative
initial fill looks like the full intended position and follow-through add-ons
are undersized or never diagnosable.
"""

from __future__ import annotations

from typing import Any


INTENDED_SHARE_FIELDS = (
    "original_shares",
    "intended_shares",
    "target_shares",
    "signal_suggested_shares",
    "planned_entry_shares",
)


def _as_positive_int(value: Any) -> int | None:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def resolve_intended_shares(position: dict | None) -> tuple[int | None, str | None]:
    """Return the first usable intended-share value and its field name."""
    if not isinstance(position, dict):
        return None, None
    for field in INTENDED_SHARE_FIELDS:
        shares = _as_positive_int(position.get(field))
        if shares is not None:
            return shares, field
    return None, None


def audit_position_intent_coverage(open_positions: dict | None) -> dict:
    """Audit whether non-legacy positions can support conservative-entry top-ups."""
    positions = (open_positions or {}).get("positions", []) or []
    missing = []
    invalid = []
    underfilled = []
    with_intent = 0
    auditable = 0

    for pos in positions:
        if not isinstance(pos, dict):
            continue
        ticker = str(pos.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        try:
            current_shares = float(pos.get("shares") or 0)
        except (TypeError, ValueError):
            current_shares = 0.0
        if current_shares <= 0:
            continue

        opened_by = str(pos.get("opened_by_strategy") or "").lower().strip()
        if opened_by == "legacy":
            continue

        auditable += 1
        intended, source = resolve_intended_shares(pos)
        if intended is None:
            missing.append(ticker)
            for field in INTENDED_SHARE_FIELDS:
                raw_value = pos.get(field)
                if raw_value is not None and _as_positive_int(raw_value) is None:
                    invalid.append({
                        "ticker": ticker,
                        "field": field,
                        "value": raw_value,
                    })
            continue

        with_intent += 1
        if current_shares < intended:
            underfilled.append({
                "ticker": ticker,
                "current_shares": current_shares,
                "intended_shares": intended,
                "shortfall_shares": intended - current_shares,
                "source_field": source,
            })

    coverage_pct = (with_intent / auditable) if auditable else 1.0
    return {
        "purpose": "conservative_entry_top_up_readiness",
        "accepted_intended_share_fields": list(INTENDED_SHARE_FIELDS),
        "non_legacy_positions": auditable,
        "positions_with_intended_shares": with_intent,
        "coverage_pct": round(coverage_pct, 4),
        "missing_intended_share_tickers": missing,
        "invalid_intended_share_fields": invalid,
        "underfilled_positions": underfilled,
    }
