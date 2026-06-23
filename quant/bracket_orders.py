"""Daily resting bracket-order playbook (default-off, OUTPUT ONLY).

Purpose
-------
The backtester and production exit logic model each position as a market-on-open
entry plus a resting GTC bracket: a SELL LIMIT at ``target_price`` (filled when
the daily high reaches it) and a SELL STOP at ``stop_price`` (filled when the
daily low reaches it). That model is only realistic if those resting orders are
actually placed with the broker. This module turns the operator's
``open_positions.json`` levels into the exact resting orders to place/maintain so
live execution matches the modeled fills.

It NEVER submits orders. It produces a structured plan + a human-readable section;
the operator (or their own confirmed automation) places the orders.

Validation
----------
A long bracket is only sane when ``stop_price < current_price < target_price``.
Each leg is classified, and corrupt levels (e.g. a stop above the target) are
flagged as warnings and NOT emitted as orders.
"""

from __future__ import annotations

from typing import Any

GTC = "GTC"


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # drop NaN


def _qty(shares: Any) -> float | int | None:
    f = _num(shares)
    if f is None or f <= 0:
        return None
    return int(f) if float(f).is_integer() else round(f, 4)


def _positions(open_positions: Any) -> list[dict]:
    if isinstance(open_positions, dict):
        rows = open_positions.get("positions") or open_positions.get("open_positions") or []
    elif isinstance(open_positions, list):
        rows = open_positions
    else:
        rows = []
    return [r for r in rows if isinstance(r, dict)]


def _prior_stop_prices(prior_orders: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(prior_orders, dict):
        return out
    for order in prior_orders.get("orders") or []:
        if not isinstance(order, dict):
            continue
        if order.get("leg") == "stop" and order.get("action") in {"PLACE", "MOVE"}:
            px = _num(order.get("price"))
            tic = str(order.get("ticker") or "").upper()
            if tic and px is not None:
                out[tic] = px
    return out


def build_bracket_orders(
    open_positions: Any,
    current_prices: dict[str, Any] | None = None,
    *,
    asof_date: str,
    prior_orders: dict | None = None,
) -> dict[str, Any]:
    """Build the resting bracket-order plan for the day.

    Returns a dict with ``orders`` (each PLACE/MOVE order is a resting GTC order
    to have at the broker), ``warnings`` (corrupt/missing levels), and a
    ``summary``. ``current_prices`` maps ticker -> latest close; when a price is
    missing the leg is still emitted but flagged for manual verification.
    """
    prices = {str(k).upper(): _num(v) for k, v in (current_prices or {}).items()}
    prior_stop = _prior_stop_prices(prior_orders)
    orders: list[dict[str, Any]] = []
    warnings: list[str] = []
    runners = 0

    for pos in _positions(open_positions):
        ticker = str(pos.get("ticker") or "").upper()
        if not ticker:
            continue
        qty = _qty(pos.get("shares"))
        if qty is None:
            continue
        avg_cost = _num(pos.get("avg_cost"))
        target = _num(pos.get("target_price"))
        stop = _num(pos.get("stop_price"))
        px = prices.get(ticker)

        def _base(order_type: str, price: float, leg: str, action: str, note: str) -> dict[str, Any]:
            return {
                "ticker": ticker,
                "side": "SELL",
                "order_type": order_type,
                "price": round(price, 2),
                "quantity": qty,
                "tif": GTC,
                "leg": leg,
                "action": action,
                "current_price": px,
                "avg_cost": avg_cost,
                "note": note,
            }

        # ---- TARGET leg: resting SELL LIMIT at target_price -----------------
        # A long limit-sell only rests ABOVE market. If price is already past the
        # recorded target, either the target is stale on a runner (price far above,
        # protected by a trailing stop) or it just hit with no protection.
        if target is None or target <= 0:
            warnings.append(f"{ticker}: no usable target_price - no profit-target order emitted.")
        elif avg_cost is not None and target <= avg_cost:
            warnings.append(
                f"{ticker}: target_price {target:.2f} <= avg_cost {avg_cost:.2f} "
                "(not a profit target) - skipped, verify the level."
            )
        elif px is not None and px >= target:
            if stop is not None and 0 < stop < px:
                runners += 1
                warnings.append(
                    f"{ticker}: price {px:.2f} is past recorded target {target:.2f} - runner managed "
                    f"by trailing stop {stop:.2f}; no resting limit emitted. Raise target_price to set a ceiling."
                )
            else:
                orders.append(_base(
                    "LIMIT", target, "target", "EXIT_NOW",
                    f"current {px:.2f} >= target {target:.2f} and no protective stop below market - "
                    "target reached, exit now.",
                ))
        else:
            note = "resting profit-target sell; place once and leave."
            if px is None:
                note += " (current price unavailable - verify it is below target)"
            orders.append(_base("LIMIT", target, "target", "PLACE", note))

        # ---- STOP leg: resting SELL STOP at stop_price ----------------------
        # A long sell-stop only rests BELOW market. stop >= current price means the
        # stop is already breached (price fell to/through it) -> exit now.
        if stop is None or stop <= 0:
            warnings.append(f"{ticker}: no usable stop_price - no stop order emitted.")
        elif px is not None and stop >= px:
            orders.append(_base(
                "STOP", stop, "stop", "EXIT_NOW",
                f"current {px:.2f} <= stop {stop:.2f}; stop already breached - exit now "
                "(cannot rest a sell-stop at/above market).",
            ))
        else:
            prior = prior_stop.get(ticker)
            if prior is not None and abs(prior - stop) >= 0.01:
                action = "MOVE"
                note = f"trailing stop moved {prior:.2f} -> {stop:.2f}; cancel old stop and replace."
            else:
                action = "PLACE"
                note = "resting protective stop; place once, move up only as it trails."
            if px is None:
                note += " (current price unavailable - verify it is below market)"
                if target is not None and stop >= target:
                    note += " [stop>=recorded target: runner if target is stale, else verify]"
            orders.append(_base("STOP", stop, "stop", action, note))

    place = [o for o in orders if o["action"] in {"PLACE", "MOVE"}]
    exit_now = [o for o in orders if o["action"] == "EXIT_NOW"]
    summary = {
        "positions": len(_positions(open_positions)),
        "resting_orders_to_maintain": len(place),
        "target_limits": len([o for o in place if o["leg"] == "target"]),
        "protective_stops": len([o for o in place if o["leg"] == "stop"]),
        "exit_now_flags": len(exit_now),
        "past_target_runners": runners,
        "warnings": len(warnings),
    }
    return {
        "asof_date": asof_date,
        "sleeve": "RESTING_BRACKET_ORDERS",
        "policy": "output_only_operator_places_orders",
        "orders": orders,
        "warnings": warnings,
        "summary": summary,
    }


def render_bracket_orders_section(plan: dict[str, Any]) -> str:
    """Render the human-readable report section for the bracket-order plan."""
    if not isinstance(plan, dict):
        return ""
    lines: list[str] = []
    lines.append("\n" + "-" * 60)
    lines.append("BRACKET ORDERS TO MAINTAIN (resting GTC; place yourself)")
    lines.append("-" * 60)
    s = plan.get("summary", {})
    lines.append(
        f"  Positions: {s.get('positions', 0)}  |  Resting orders: {s.get('resting_orders_to_maintain', 0)} "
        f"({s.get('target_limits', 0)} target-limit, {s.get('protective_stops', 0)} stop)  |  "
        f"Exit-now flags: {s.get('exit_now_flags', 0)}  |  Warnings: {s.get('warnings', 0)}"
    )
    lines.append("  These make backtest/production fills real; run.py does NOT submit them.")

    place = [o for o in plan.get("orders", []) if o.get("action") in {"PLACE", "MOVE"}]
    exit_now = [o for o in plan.get("orders", []) if o.get("action") == "EXIT_NOW"]
    if place:
        lines.append("")
        lines.append("  MAINTAIN these resting orders:")
        for o in sorted(place, key=lambda r: (r["ticker"], r["leg"])):
            tag = "MOVE" if o["action"] == "MOVE" else "    "
            lines.append(
                f"    {tag} {o['ticker']:6} SELL {o['order_type']:5} @ {o['price']:>10.2f} "
                f"x{o['quantity']} {o['tif']}  [{o['leg']}]"
            )
    if exit_now:
        lines.append("")
        lines.append("  EXIT NOW (level already reached - resting order can't capture it):")
        for o in sorted(exit_now, key=lambda r: (r["ticker"], r["leg"])):
            lines.append(f"    {o['ticker']:6} {o['leg']:6} {o['note']}")
    for w in plan.get("warnings", []):
        lines.append(f"  ! {w}")
    return "\n".join(lines)
