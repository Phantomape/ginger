"""Deterministic guardrails for discretionary intraday position triage.

The helper emits allowed actions and a safe default action.  It never emits an
order and never promotes ``ADD_SMALL`` by itself; news/human review may select
that action only when it is explicitly present in ``allowed_actions``.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from intraday_moomoo import (
        LEVERAGED_PRODUCTS,
        market_proxy_for,
        sector_proxy_for,
        underlying_for,
    )
    from open_position_schema import account_positions
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.intraday_moomoo import (
        LEVERAGED_PRODUCTS,
        market_proxy_for,
        sector_proxy_for,
        underlying_for,
    )
    from quant.open_position_schema import account_positions


def _number(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _confirmed_above_vwap(metrics: dict | None) -> bool | None:
    metrics = metrics or {}
    price = _number(metrics.get("reference_price"))
    vwap = _number(metrics.get("rth_vwap"))
    if price is None or vwap is None:
        return None
    return price > vwap


def _add_size_cap(ticker: str, atr_pct: float | None) -> float:
    if ticker in LEVERAGED_PRODUCTS or (atr_pct is not None and atr_pct >= 0.08):
        return 0.10
    if atr_pct is not None and atr_pct >= 0.05:
        return 0.15
    return 0.20


def _levels(metrics: dict) -> tuple[float | None, float | None]:
    candidates = [
        _number(metrics.get("rth_vwap")),
        _number(metrics.get("ema8")),
        _number(metrics.get("sma20")),
    ]
    candidates = [value for value in candidates if value is not None]
    confirmation = max(candidates) if candidates else None
    invalidation = _number(metrics.get("rth_vwap")) or _number(metrics.get("rth_low"))
    return confirmation, invalidation


def build_machine_triage(
    open_positions: dict,
    position_reviews: list[dict],
    opend_context: dict,
    *,
    portfolio_heat: dict | None,
    accounting: dict | None,
    pending_actions: list[dict] | None = None,
) -> dict:
    """Build one deterministic advisory row for every real account holding."""
    review_by_ticker = {
        str(row.get("ticker") or "").upper(): row
        for row in position_reviews or []
        if row.get("ticker")
    }
    ticker_data = opend_context.get("tickers") or {}
    phase = str(opend_context.get("market_phase") or "UNKNOWN")
    cash = _number((accounting or {}).get("cash_usd"))
    portfolio_value = _number((accounting or {}).get("portfolio_value_usd"))
    if cash is None:
        cash = _number(open_positions.get("cash_usd"))
    if portfolio_value is None:
        portfolio_value = _number(open_positions.get("portfolio_value_usd"))
    cash_pct = cash / portfolio_value if cash is not None and portfolio_value else None
    heat_pct = _number((portfolio_heat or {}).get("portfolio_heat_pct"))
    heat_cap = _number((portfolio_heat or {}).get("max_heat_pct"))
    pending_by_ticker: dict[str, list[str]] = {}
    for action in pending_actions or []:
        ticker = str(action.get("ticker") or "").upper()
        name = str(action.get("action") or "").upper()
        if ticker and name in {"EXIT", "REDUCE", "TIGHTEN_STOP"}:
            pending_by_ticker.setdefault(ticker, []).append(name)

    rows: list[dict[str, Any]] = []
    for position in account_positions(open_positions, positive_only=True):
        ticker = str(position.get("ticker") or "").upper()
        review = review_by_ticker.get(ticker, {})
        metrics = (ticker_data.get(ticker) or {}).get("metrics") or {}
        underlying = underlying_for(ticker)
        sector_proxy = sector_proxy_for(ticker)
        market_proxy = market_proxy_for(ticker)
        blockers: list[str] = []
        risk_blocks: list[str] = []

        if review.get("status") == "BREACHED":
            primary = review.get("primary_advisory_shadow_action") or {}
            shadow_action = str(primary.get("shadow_action") or "").upper()
            if shadow_action == "REVIEW":
                machine_state = "RULE_REVIEW_REQUIRED"
                default_action = "HOLD_ONLY"
                allowed_actions = ["HOLD_ONLY", "REDUCE_RISK"]
                block_name = "existing_rule_review_required"
            else:
                machine_state = "RISK_ACTION_REQUIRED"
                default_action = "REDUCE_RISK"
                allowed_actions = ["REDUCE_RISK"]
                block_name = "existing_exit_rule_breached"
            rows.append({
                "ticker": ticker,
                "position_group": position.get("position_group"),
                "underlying": underlying,
                "sector_proxy": sector_proxy,
                "market_proxy": market_proxy,
                "machine_state": machine_state,
                "default_action": default_action,
                "allowed_actions": allowed_actions,
                "blockers": [block_name],
                "risk_blocks": [block_name],
                "reference_price": metrics.get("reference_price") or (review.get("quote") or {}).get("price"),
                "confirmation_level": None,
                "invalidation_level": None,
                "max_add_pct_existing_position": 0.0,
                "trade_enabled": False,
            })
            continue

        if opend_context.get("status") not in {"ok", "partial"}:
            blockers.append("opend_unavailable")
        if not metrics.get("technical_context_complete"):
            blockers.append("technical_context_incomplete")
        if phase != "RTH":
            blockers.append("outside_rth")
        if review.get("status") in {"QUOTE_UNAVAILABLE", "NO_CONTEXT"}:
            blockers.append("position_review_incomplete")
        if (review.get("quote") or {}).get("is_stale"):
            blockers.append("stale_position_quote")

        price = _number(metrics.get("reference_price"))
        rth_vwap = _number(metrics.get("rth_vwap"))
        ema8 = _number(metrics.get("ema8"))
        sma20 = _number(metrics.get("sma20"))
        range_location = _number(metrics.get("rth_range_location"))
        atr_pct = _number(metrics.get("atr_pct"))

        if price is not None and rth_vwap is not None and price <= rth_vwap:
            blockers.append("below_rth_vwap")
        if price is not None and ema8 is not None and price <= ema8:
            blockers.append("below_ema8")
        if price is not None and sma20 is not None and price <= sma20:
            blockers.append("below_sma20")
        if range_location is not None and range_location < 0.55:
            blockers.append("weak_rth_range_location")

        atr_limit = 0.20 if ticker in LEVERAGED_PRODUCTS else 0.12
        if atr_pct is not None and atr_pct > atr_limit:
            blockers.append("atr_risk_too_high_for_add_review")

        target_distance = _number(review.get("distance_to_target_pct"))
        if target_distance is not None and 0 <= target_distance <= 0.02:
            risk_blocks.append("near_existing_target")
        proximity_flags = set(review.get("proximity_flags") or [])
        if proximity_flags & {"NEAR_HARD_STOP", "NEAR_ATR_STOP", "NEAR_TRAILING_STOP"}:
            risk_blocks.append("near_existing_stop")
        if ticker in pending_by_ticker:
            risk_blocks.append("pending_risk_action_open")
        if heat_pct is not None and heat_cap is not None and heat_pct >= heat_cap:
            risk_blocks.append("portfolio_heat_at_cap")
        if cash_pct is not None and cash_pct < 0.05:
            risk_blocks.append("cash_below_5pct")

        proxy_checks = {
            "underlying_above_rth_vwap": _confirmed_above_vwap(
                (ticker_data.get(underlying) or {}).get("metrics")
            ) if underlying else None,
            "sector_proxy_above_rth_vwap": _confirmed_above_vwap(
                (ticker_data.get(sector_proxy) or {}).get("metrics")
            ),
            "market_proxy_above_rth_vwap": _confirmed_above_vwap(
                (ticker_data.get(market_proxy) or {}).get("metrics")
            ),
        }
        for key, value in proxy_checks.items():
            if key.startswith("underlying") and underlying is None:
                continue
            if value is not True:
                blockers.append(f"{key}_not_confirmed")

        confirmation, invalidation = _levels(metrics)
        allowed = ["HOLD_ONLY", "WAIT"]
        eligible = not blockers and not risk_blocks
        if eligible:
            allowed.append("ADD_SMALL")
        if risk_blocks:
            state = "HOLD_ONLY"
            default_action = "HOLD_ONLY"
        elif eligible:
            state = "ADD_REVIEW_ELIGIBLE"
            default_action = "WAIT"
        else:
            state = "WAIT_FOR_CONFIRMATION"
            default_action = "WAIT"

        rows.append({
            "ticker": ticker,
            "position_group": position.get("position_group"),
            "underlying": underlying,
            "sector_proxy": sector_proxy,
            "market_proxy": market_proxy,
            "machine_state": state,
            "default_action": default_action,
            "allowed_actions": allowed,
            "blockers": sorted(set(blockers)),
            "risk_blocks": sorted(set(risk_blocks)),
            "proxy_confirmation": proxy_checks,
            "pending_risk_actions": pending_by_ticker.get(ticker, []),
            "reference_price": price,
            "confirmation_level": round(confirmation, 4) if confirmation is not None else None,
            "invalidation_level": round(invalidation, 4) if invalidation is not None else None,
            "max_add_pct_existing_position": _add_size_cap(ticker, atr_pct) if eligible else 0.0,
            "atr_pct": atr_pct,
            "trade_enabled": False,
        })

    return {
        "schema_version": 1,
        "policy": "discretionary_intraday_guardrails_v1",
        "market_phase": phase,
        "cash_pct": round(cash_pct, 6) if cash_pct is not None else None,
        "portfolio_heat_pct": heat_pct,
        "portfolio_heat_cap_pct": heat_cap,
        "rows": rows,
        "add_review_eligible": [
            row["ticker"] for row in rows if "ADD_SMALL" in row["allowed_actions"]
        ],
        "trade_enabled": False,
        "strategy_behavior_changed": False,
    }


def build_decision_template(machine_triage: dict, *, timestamp_et: str,
                            raw_snapshot_ref: str) -> dict:
    """Create a safe, structured template for the final discretionary decision."""
    rows = []
    for row in machine_triage.get("rows") or []:
        rows.append({
            "timestamp_et": timestamp_et,
            "market_phase": machine_triage.get("market_phase"),
            "agent": "pending_discretionary_review",
            "user_question": "scheduled_intraday_all_positions_triage",
            "ticker": row.get("ticker"),
            "underlying": row.get("underlying"),
            "sector_proxy": row.get("sector_proxy"),
            "market_proxy": row.get("market_proxy"),
            "action_label": row.get("default_action"),
            "allowed_actions": row.get("allowed_actions"),
            "confidence": None,
            "reference_price": row.get("reference_price"),
            "entry_condition": {
                "confirmation_level": row.get("confirmation_level"),
                "machine_state": row.get("machine_state"),
            },
            "invalidation_level": row.get("invalidation_level"),
            "time_horizon": "RTH_CLOSE",
            "raw_snapshot_ref": raw_snapshot_ref,
            "news_refs": [],
            "notes": {
                "blockers": row.get("blockers"),
                "risk_blocks": row.get("risk_blocks"),
                "max_add_pct_existing_position": row.get("max_add_pct_existing_position"),
                "requires_news_review": True,
            },
        })
    return {
        "schema_version": 1,
        "status": "decision_template_pending_news_review",
        "immutable_after_finalization": True,
        "trade_enabled": False,
        "rows": rows,
    }


def finalize_decision_payload(template: dict, semantic_response: dict) -> dict:
    """Validate semantic decisions against code-owned allowed actions."""
    template_rows = template.get("rows") or []
    response_rows = semantic_response.get("decisions") or []
    expected = [str(row.get("ticker") or "").upper() for row in template_rows]
    received = [str(row.get("ticker") or "").upper() for row in response_rows]
    if len(received) != len(set(received)):
        raise ValueError("duplicate ticker in semantic decisions")
    if set(received) != set(expected):
        missing = sorted(set(expected) - set(received))
        extra = sorted(set(received) - set(expected))
        raise ValueError(f"decision ticker mismatch: missing={missing} extra={extra}")

    response_by_ticker = {
        str(row.get("ticker") or "").upper(): row for row in response_rows
    }
    finalized = []
    for template_row in template_rows:
        ticker = str(template_row.get("ticker") or "").upper()
        semantic = response_by_ticker[ticker]
        action = str(semantic.get("action_label") or "").upper()
        allowed = [str(value).upper() for value in template_row.get("allowed_actions") or []]
        if action not in allowed:
            raise ValueError(f"{ticker}: action {action!r} not in allowed_actions={allowed}")
        confidence = _number(semantic.get("confidence"))
        if confidence is None or not 0.0 <= confidence <= 1.0:
            raise ValueError(f"{ticker}: confidence must be between 0 and 1")
        news_refs = semantic.get("news_refs") or []
        if not isinstance(news_refs, list):
            raise ValueError(f"{ticker}: news_refs must be a list")
        if action == "ADD_SMALL" and not news_refs:
            raise ValueError(f"{ticker}: ADD_SMALL requires at least one verified news_ref")
        reason = str(semantic.get("reason") or "").strip()
        if not reason:
            raise ValueError(f"{ticker}: reason is required")

        row = dict(template_row)
        row.update({
            "agent": "codex_intraday_semantic_reviewer",
            "action_label": action,
            "confidence": round(confidence, 4),
            "news_refs": news_refs,
            "news_veto": bool(semantic.get("news_veto")),
            "reason": reason,
        })
        finalized.append(row)

    return {
        "schema_version": 1,
        "status": "finalized_discretionary_forward_decision",
        "finalized_at_et": datetime.now(ZoneInfo("America/New_York")).strftime(
            "%Y-%m-%d %H:%M:%S ET"
        ),
        "portfolio_summary": str(semantic_response.get("portfolio_summary") or "").strip(),
        "immutable": True,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "rows": finalized,
    }


def persist_final_decision(payload: dict, output_dir: str | Path) -> Path:
    """Persist a finalized ledger with exclusive-create semantics."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    now_et = datetime.now(ZoneInfo("America/New_York"))
    base = now_et.strftime("intraday_triage_%Y%m%d_%H%M%SET")
    for suffix in range(100):
        name = f"{base}.json" if suffix == 0 else f"{base}_{suffix:02d}.json"
        path = output_dir / name
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            return path
        except FileExistsError:
            continue
    raise FileExistsError("could not allocate a unique intraday decision filename")
