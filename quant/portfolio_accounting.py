"""Shared portfolio accounting helpers.

The daily operator should not have to maintain cash_usd by hand when the
account-level portfolio_value_usd is already known.  This module gives run.py
and llm_advisor.py one shared path for deriving cash and portfolio value from
open_positions plus current prices.
"""

from __future__ import annotations


def _to_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_equity_market_value(open_positions: dict | None, current_prices: dict | None) -> float:
    """Return market value of listed open positions using current prices when available."""
    total = 0.0
    for pos in (open_positions or {}).get("positions", []) or []:
        ticker = pos.get("ticker")
        shares = _to_float(pos.get("shares"), 0.0)
        if not ticker or shares <= 0:
            continue
        price = _to_float((current_prices or {}).get(ticker), None)
        if price is None:
            price = _to_float(pos.get("avg_cost"), 0.0)
        total += shares * price
    return total


def resolve_portfolio_accounting(
    open_positions: dict | None,
    current_prices: dict | None,
    stored_portfolio_value: float | None = None,
    logger=None,
) -> dict:
    """Resolve portfolio value, equity value, and cash without requiring cash_usd.

    Precedence:
      1. If cash_usd is present, portfolio value = equity market value + cash_usd.
      2. If cash_usd is absent but portfolio_value_usd is present, derive cash as
         portfolio_value_usd - equity market value and keep portfolio_value_usd
         as the sizing/heat denominator.
      3. If both are absent, fall back to equity-only with a warning.
    """
    open_positions = open_positions or {}
    equity_value = compute_equity_market_value(open_positions, current_prices)
    stored_value = _to_float(
        stored_portfolio_value
        if stored_portfolio_value is not None
        else open_positions.get("portfolio_value_usd"),
        None,
    )
    cash_raw = open_positions.get("cash_usd")
    cash_value = _to_float(cash_raw, None)
    warnings = []

    if cash_value is not None:
        portfolio_value = equity_value + cash_value
        cash_source = "explicit_cash_usd"
        if stored_value and abs(portfolio_value - stored_value) / max(stored_value, 1) > 0.15:
            warnings.append(
                "Portfolio value drift: stored portfolio_value_usd differs from "
                "equity market value + explicit cash_usd by more than 15%."
            )
    elif stored_value is not None:
        derived_cash = stored_value - equity_value
        cash_value = max(0.0, derived_cash)
        portfolio_value = stored_value
        cash_source = "derived_from_portfolio_value_usd"
        if derived_cash < 0:
            warnings.append(
                "Derived cash is negative because equity market value exceeds "
                "portfolio_value_usd; using cash_usd=0 for display while keeping "
                "portfolio_value_usd as the denominator."
            )
    elif equity_value > 0:
        cash_value = 0.0
        portfolio_value = equity_value
        cash_source = "equity_only_missing_portfolio_value"
        warnings.append(
            "portfolio_value_usd and cash_usd are both missing; using listed "
            "equity market value only. Cash cannot be inferred."
        )
    else:
        cash_value = None
        portfolio_value = None
        cash_source = "unavailable"
        warnings.append(
            "No portfolio_value_usd, cash_usd, or priced positions available."
        )

    for msg in warnings:
        if logger:
            logger.warning(msg)

    return {
        "portfolio_value_usd": round(portfolio_value, 2) if portfolio_value is not None else None,
        "equity_market_value_usd": round(equity_value, 2),
        "cash_usd": round(cash_value, 2) if cash_value is not None else None,
        "cash_source": cash_source,
        "cash_is_inferred": cash_source == "derived_from_portfolio_value_usd",
        "warnings": warnings,
    }
