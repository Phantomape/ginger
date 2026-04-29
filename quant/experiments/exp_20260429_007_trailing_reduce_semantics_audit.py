#!/usr/bin/env python
"""
Shadow audit for repeated TRAILING_STOP partial-reduce semantics.

This runner is intentionally read-only with respect to production state.  It
uses archived daily advice/prompt artifacts to estimate whether repeated
TRAILING_STOP reduces are distinct new risk events or repeated handling of the
same breach.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


EXP_ID = "exp-20260429-007"
DATA_DIR = Path("data")
OUT_PATH = DATA_DIR / "experiments" / EXP_ID / "exp_20260429_007_trailing_reduce_semantics_audit.json"


@dataclass
class TrailingEvent:
    date: str
    ticker: str
    action: str
    rule: str
    shares_to_sell: int
    suggested_reduce_pct: int | None
    current_shares: float | None
    current_price: float | None
    trailing_stop: float | None
    high_water_mark: float | None
    drawdown_from_high_pct: float | None
    unrealized_pnl_pct: float | None
    decision_mode: str | None
    reason: str | None
    prior_reduce_dates: list[str]
    prior_reduce_rules: list[str]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _extract_actions(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("position_actions"), list):
        return payload["position_actions"]
    advice = payload.get("advice")
    if isinstance(advice, dict) and isinstance(advice.get("position_actions"), list):
        return advice["position_actions"]
    return []


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _prompt_context(date: str, ticker: str) -> dict[str, float | None]:
    """Best-effort extraction from archived prompt text."""
    path = DATA_DIR / f"llm_prompt_{date}.txt"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")

    ctx: dict[str, float | None] = {}
    ticker_pat = re.escape(ticker)

    # Use the positions_requiring_attention block when available because it has
    # current_price, shares, unrealized PnL, drawdown, and stop messages close
    # together.  Keep the window small enough to avoid cross-ticker capture.
    blocks = [
        m.group(0)
        for m in re.finditer(
            rf'"ticker"\s*:\s*"{ticker_pat}".{{0,2400}}?(?=\n\s*\{{\s*"ticker"|\n\s*\]\s*,|\Z)',
            text,
            flags=re.S,
        )
    ]
    block = ""
    for candidate in blocks:
        if '"current_price"' in candidate or "trailing stop" in candidate:
            block = candidate
            break
    if not block and blocks:
        block = blocks[0]

    def grab(name: str) -> float | None:
        mm = re.search(rf'"{name}"\s*:\s*(-?\d+(?:\.\d+)?)', block)
        return _float_or_none(mm.group(1) if mm else None)

    ctx["current_price"] = grab("current_price")
    if ctx["current_price"] is None:
        ctx["current_price"] = grab("close")
    ctx["current_shares"] = grab("shares")
    ctx["unrealized_pnl_pct"] = grab("unrealized_pnl_pct")
    ctx["drawdown_from_high_pct"] = grab("drawdown_from_20d_high_pct")
    ctx["trailing_stop"] = grab("trailing_stop_from_20d_high")

    msg = re.search(
        r"Price\s+(-?\d+(?:\.\d+)?)\s+<=\s+trailing stop\s+(-?\d+(?:\.\d+)?)"
        r"\s+\(8% from high\s+(-?\d+(?:\.\d+)?)\)",
        block,
    )
    if msg:
        ctx["current_price"] = _float_or_none(msg.group(1))
        ctx["trailing_stop"] = _float_or_none(msg.group(2))
        ctx["high_water_mark"] = _float_or_none(msg.group(3))
    else:
        ctx["high_water_mark"] = None

    return ctx


def _all_reduce_history() -> dict[str, list[dict[str, Any]]]:
    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(DATA_DIR.glob("llm_prompt_resp_*.json")):
        date = path.stem.rsplit("_", 1)[-1]
        if not ("20260401" <= date <= "20260428"):
            continue

        payload = _load_json(path)
        actions = _extract_actions(payload)
        for action in actions:
            if not isinstance(action, dict):
                continue
            if action.get("action") != "REDUCE":
                continue
            try:
                shares_to_sell = int(action.get("shares_to_sell"))
            except (TypeError, ValueError):
                continue
            if shares_to_sell <= 0:
                continue
            ticker = str(action.get("ticker") or "").upper()
            history[ticker].append({
                "date": date,
                "ticker": ticker,
                "rule": action.get("exit_rule_triggered") or "UNKNOWN",
                "shares_to_sell": shares_to_sell,
                "decision_mode": action.get("decision_mode"),
            })
    return history


def load_events() -> list[TrailingEvent]:
    events: list[TrailingEvent] = []
    all_history = _all_reduce_history()
    for path in sorted(DATA_DIR.glob("llm_prompt_resp_*.json")):
        date = path.stem.rsplit("_", 1)[-1]
        if not ("20260401" <= date <= "20260428"):
            continue

        payload = _load_json(path)
        actions = _extract_actions(payload)
        decision_log_path = DATA_DIR / f"llm_decision_log_{date}.json"
        decision_log = _load_json(decision_log_path) if decision_log_path.exists() else {}
        reduce_pct = decision_log.get("suggested_reduce_pct", {}) if isinstance(decision_log, dict) else {}

        for action in actions:
            if not isinstance(action, dict):
                continue
            if action.get("action") != "REDUCE":
                continue
            if action.get("exit_rule_triggered") != "TRAILING_STOP":
                continue
            try:
                shares_to_sell = int(action.get("shares_to_sell"))
            except (TypeError, ValueError):
                continue
            if shares_to_sell <= 0:
                continue

            ticker = str(action.get("ticker") or "").upper()
            ctx = _prompt_context(date, ticker)
            prior = [h for h in all_history.get(ticker, []) if h["date"] < date]
            events.append(
                TrailingEvent(
                    date=date,
                    ticker=ticker,
                    action="REDUCE",
                    rule="TRAILING_STOP",
                    shares_to_sell=shares_to_sell,
                    suggested_reduce_pct=reduce_pct.get(ticker),
                    current_shares=ctx.get("current_shares"),
                    current_price=ctx.get("current_price"),
                    trailing_stop=ctx.get("trailing_stop"),
                    high_water_mark=ctx.get("high_water_mark"),
                    drawdown_from_high_pct=ctx.get("drawdown_from_high_pct"),
                    unrealized_pnl_pct=ctx.get("unrealized_pnl_pct"),
                    decision_mode=action.get("decision_mode"),
                    reason=action.get("reason"),
                    prior_reduce_dates=[h["date"] for h in prior],
                    prior_reduce_rules=[h["rule"] for h in prior],
                )
            )
    return events


def _date_num(date: str) -> int:
    return int(date)


def _keep_current(event: TrailingEvent, state: dict[str, Any]) -> bool:
    return True


def _keep_one_shot(event: TrailingEvent, state: dict[str, Any]) -> bool:
    return event.ticker not in state.setdefault("seen", set())


def _keep_cooldown_5_calendar(event: TrailingEvent, state: dict[str, Any]) -> bool:
    last = state.setdefault("last", {}).get(event.ticker)
    if last is None:
        return True
    # Dates are close together in the production archive; calendar-day gap is
    # enough for detecting the immediate duplicate behavior at issue.
    return _date_num(event.date) - _date_num(last) >= 5


def _tier(drawdown: float | None) -> int | None:
    if drawdown is None:
        return None
    # drawdown is negative.  A more negative value is a deeper breach.
    if drawdown <= -0.25:
        return 3
    if drawdown <= -0.15:
        return 2
    if drawdown <= -0.08:
        return 1
    return 0


def _keep_deeper_breach_tier(event: TrailingEvent, state: dict[str, Any]) -> bool:
    tier = _tier(event.drawdown_from_high_pct)
    if tier is None:
        # Missing context: keep first event only, then suppress repeats rather
        # than pretending missing depth is new adverse information.
        return _keep_one_shot(event, state)
    last_tier = state.setdefault("max_tier", {}).get(event.ticker, -1)
    return tier > last_tier


def _keep_stop_update_only(event: TrailingEvent, state: dict[str, Any]) -> bool:
    # Alternative policy: repeated trailing breach becomes a stop-update / watch
    # instruction, not a sell instruction.  First breach is still allowed.
    return _keep_one_shot(event, state)


def _keep_any_prior_reduce_memory(event: TrailingEvent, state: dict[str, Any]) -> bool:
    # Broader execution-memory candidate: if the user already reduced this ticker
    # for any rule in the recent archive, do not issue another partial reduce for
    # a trailing breach.  This captures the TRIP 20260427 PROFIT_TARGET -> 20260428
    # TRAILING_STOP sequence that same-rule memory would miss.
    return not event.prior_reduce_dates


POLICIES = {
    "current_daily_repeat": _keep_current,
    "one_shot_per_ticker_rule": _keep_one_shot,
    "cooldown_5_calendar_days": _keep_cooldown_5_calendar,
    "deeper_breach_tiers_8_15_25": _keep_deeper_breach_tier,
    "first_reduce_then_stop_update": _keep_stop_update_only,
    "suppress_if_any_prior_reduce": _keep_any_prior_reduce_memory,
}


def simulate(events: list[TrailingEvent]) -> dict[str, Any]:
    latest_price_by_ticker: dict[str, float] = {}
    for event in events:
        if event.current_price is not None:
            latest_price_by_ticker[event.ticker] = event.current_price

    by_policy: dict[str, Any] = {}
    for name, keep_fn in POLICIES.items():
        state: dict[str, Any] = {}
        kept: list[TrailingEvent] = []
        suppressed: list[TrailingEvent] = []
        for event in events:
            keep = keep_fn(event, state)
            if keep:
                kept.append(event)
                state.setdefault("seen", set()).add(event.ticker)
                state.setdefault("last", {})[event.ticker] = event.date
                tier = _tier(event.drawdown_from_high_pct)
                if tier is not None:
                    state.setdefault("max_tier", {})[event.ticker] = max(
                        tier, state.setdefault("max_tier", {}).get(event.ticker, -1)
                    )
            else:
                suppressed.append(event)

        opportunity_delta = 0.0
        suppress_rows = []
        for event in suppressed:
            latest = latest_price_by_ticker.get(event.ticker)
            if event.current_price is None or latest is None:
                delta = None
            else:
                # Positive means suppressing the sell would have helped through
                # the latest archived price; negative means current sell avoided
                # further loss.
                delta = (latest - event.current_price) * event.shares_to_sell
                opportunity_delta += delta
            suppress_rows.append({
                "date": event.date,
                "ticker": event.ticker,
                "shares_to_sell": event.shares_to_sell,
                "price": event.current_price,
                "latest_price": latest,
                "hold_vs_sell_delta_usd_to_latest": delta,
                "drawdown_from_high_pct": event.drawdown_from_high_pct,
            })

        by_policy[name] = {
            "kept_reduce_count": len(kept),
            "kept_shares_to_sell": sum(e.shares_to_sell for e in kept),
            "suppressed_reduce_count": len(suppressed),
            "suppressed_shares_to_sell": sum(e.shares_to_sell for e in suppressed),
            "hold_vs_sell_delta_usd_to_latest": round(opportunity_delta, 2),
            "suppressed_events": suppress_rows,
        }
    return by_policy


def summarize_sequences(events: list[TrailingEvent]) -> dict[str, Any]:
    grouped: dict[str, list[TrailingEvent]] = defaultdict(list)
    for event in events:
        grouped[event.ticker].append(event)

    out: dict[str, Any] = {}
    for ticker, rows in grouped.items():
        rows = sorted(rows, key=lambda e: e.date)
        out[ticker] = {
            "event_count": len(rows),
            "dates": [r.date for r in rows],
            "total_recommended_shares_to_sell": sum(r.shares_to_sell for r in rows),
            "first_price": rows[0].current_price,
            "last_price": rows[-1].current_price,
            "min_drawdown_from_high_pct": min(
                [r.drawdown_from_high_pct for r in rows if r.drawdown_from_high_pct is not None],
                default=None,
            ),
            "rows": [asdict(r) for r in rows],
        }
    return out


def main() -> None:
    events = load_events()
    result = {
        "experiment_id": EXP_ID,
        "status": "observed_only",
        "hypothesis": (
            "Current trailing-stop partial reduce may over-repeat the same risk event; "
            "stateful repeat-trigger semantics may reduce repeated sell advice without "
            "materially increasing downside risk."
        ),
        "date_range": {"start": "2026-04-01", "end": "2026-04-28"},
        "single_causal_variable": "trailing-stop repeated partial-reduce execution semantics",
        "input_files": {
            "llm_prompt_resp": len(list(DATA_DIR.glob("llm_prompt_resp_202604*.json"))),
            "llm_decision_log": len(list(DATA_DIR.glob("llm_decision_log_202604*.json"))),
        },
        "event_count": len(events),
        "unique_tickers": sorted({e.ticker for e in events}),
        "events": [asdict(e) for e in events],
        "sequences_by_ticker": summarize_sequences(events),
        "policy_comparison": simulate(events),
        "interpretation": {
            "production_issue": (
                "The current daily-repeat semantics treats each archived day below the "
                "same trailing stop as a fresh REDUCE event. This can repeatedly trim a "
                "position after the user already reflected the prior advice in "
                "open_positions."
            ),
            "best_default_candidate": (
                "Use stateful one-shot handling for a ticker/rule breach, with a second "
                "reduce only when a deeper drawdown tier is crossed or a different "
                "higher-severity rule fires."
            ),
            "not_a_strategy_promotion": (
                "This archive is too short for alpha acceptance; it is a production "
                "execution-semantics audit that identifies the duplicate-advice risk."
            ),
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXP_ID,
        "events": result["event_count"],
        "unique_tickers": result["unique_tickers"],
        "artifact": str(OUT_PATH),
        "policy_summary": {
            k: {kk: vv for kk, vv in v.items() if kk != "suppressed_events"}
            for k, v in result["policy_comparison"].items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
