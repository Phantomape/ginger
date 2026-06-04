"""Schema helpers for operator-maintained open positions.

The operator file may group real account holdings into multiple lists such as
``positions``, ``core_positions``, and ``observations``. Production risk and
exit paths should see all real holdings, while core slot accounting should only
count rows that explicitly consume core capacity.
"""

from __future__ import annotations

from typing import Iterable


ACCOUNT_POSITION_GROUPS = ("positions", "core_positions", "observations")
CORE_POSITION_GROUPS = ("core_positions",)

CORE_STRATEGY_POSITION_TAGS = frozenset({
    "trend_long",
    "breakout_long",
    "earnings_event_long",
})
CORE_SLOT_POLICIES = frozenset({
    "core",
    "core_slot",
    "consumes_core_slot",
    "consume_core_slot",
})
NON_CORE_SLOT_POLICIES = frozenset({
    "none",
    "no_core_slot",
    "does_not_consume_core_slot",
    "do_not_consume_core_slot",
    "ignore_core_slot",
})
CORE_SLEEVES = frozenset({
    "core",
    "core_strategy",
})
NON_CORE_SLEEVES = frozenset({
    "legacy",
    "manual",
    "discretionary",
    "fomo",
    "pilot",
    "paper",
    "paper_shadow",
    "observation",
    "observe_only",
})


def _normalised_text(value) -> str:
    return str(value or "").strip().lower()


def _position_strategy_tag(position: dict | None) -> str | None:
    if not isinstance(position, dict):
        return None
    for key in (
        "opened_by_strategy",
        "strategy",
        "entry_strategy",
        "source_strategy",
    ):
        value = position.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def infer_position_sleeve(position: dict | None, group: str | None = None) -> str:
    """Infer a stable sleeve label for a row that may omit ``sleeve``."""
    position = position or {}
    sleeve = _normalised_text(position.get("sleeve"))
    if sleeve:
        return sleeve
    group = _normalised_text(group or position.get("position_group"))
    if group in CORE_POSITION_GROUPS:
        return "core_strategy"
    if group == "observations":
        return "observation"

    tag = _normalised_text(_position_strategy_tag(position))
    if tag in CORE_STRATEGY_POSITION_TAGS:
        return "core_strategy"
    if tag.startswith("pilot"):
        return "pilot"
    if tag in NON_CORE_SLEEVES:
        return tag
    return "unknown"


def position_consumes_core_slot(position: dict | None, group: str | None = None) -> bool:
    """Return whether a row should consume core strategy entry capacity."""
    if not isinstance(position, dict):
        return False
    slot_policy = _normalised_text(position.get("slot_policy"))
    if slot_policy in CORE_SLOT_POLICIES:
        return True
    if slot_policy in NON_CORE_SLOT_POLICIES:
        return False

    sleeve = infer_position_sleeve(position, group)
    if sleeve in CORE_SLEEVES:
        return True
    if sleeve in NON_CORE_SLEEVES:
        return False

    tag = _normalised_text(_position_strategy_tag(position))
    return tag in CORE_STRATEGY_POSITION_TAGS


def _position_groups(payload: dict | None, group_names: Iterable[str]):
    payload = payload or {}
    for group in group_names:
        rows = payload.get(group) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                yield group, row


def normalise_position_row(position: dict, group: str | None = None) -> dict:
    """Return a shallow copy with explicit group/sleeve/slot policy metadata."""
    row = dict(position)
    if group and not row.get("position_group"):
        row["position_group"] = group
    sleeve = infer_position_sleeve(row, group)
    row.setdefault("sleeve", sleeve)
    if not row.get("slot_policy"):
        row["slot_policy"] = (
            "consumes_core_slot"
            if position_consumes_core_slot(row, group)
            else "no_core_slot"
        )
    return row


def account_positions(payload: dict | None, *, positive_only: bool = False) -> list[dict]:
    """Return all real account holdings across supported operator groups."""
    rows = [
        normalise_position_row(row, group)
        for group, row in _position_groups(payload, ACCOUNT_POSITION_GROUPS)
    ]
    if not positive_only:
        return rows
    return [
        row for row in rows
        if row.get("ticker") and _positive_number(row.get("shares")) > 0
    ]


def core_slot_positions(payload: dict | None, *, positive_only: bool = True) -> list[dict]:
    """Return positions that consume core strategy entry slots."""
    rows = [
        row for row in account_positions(payload, positive_only=positive_only)
        if position_consumes_core_slot(row, row.get("position_group"))
    ]
    return rows


def account_position_tickers(payload: dict | None, *, positive_only: bool = False) -> set[str]:
    return {
        str(row.get("ticker") or "").upper().strip()
        for row in account_positions(payload, positive_only=positive_only)
        if row.get("ticker")
    }


def positions_by_ticker(payload: dict | None, *, positive_only: bool = False) -> dict[str, dict]:
    by_ticker: dict[str, dict] = {}
    for row in account_positions(payload, positive_only=positive_only):
        ticker = str(row.get("ticker") or "").upper().strip()
        if ticker and ticker not in by_ticker:
            by_ticker[ticker] = row
    return by_ticker


def has_account_positions(payload: dict | None, *, positive_only: bool = False) -> bool:
    return bool(account_positions(payload, positive_only=positive_only))


def legacy_positions_payload(payload: dict | None) -> dict:
    """Return a copy whose ``positions`` key contains all account holdings.

    This is useful for presentation layers and old call sites that only know
    the legacy single-list shape.
    """
    if not isinstance(payload, dict):
        return {"positions": []}
    out = dict(payload)
    out["positions"] = account_positions(payload)
    return out


def _positive_number(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
