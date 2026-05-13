"""exp-20260513-008: legacy explicit-target lifecycle replay.

Backtest-style measurement repair for the production-only legacy target issue
found in exp-20260513-005.  The canonical fixed-window backtester already
executes simulated ``target_price`` exits, so it cannot test the live
``legacy_basis`` advisory guard.  This experiment instead replays saved daily
``trend_signals_*.json`` position contexts and asks:

* If an explicit target was reached but hidden by ``legacy_basis``, would a
  full exit, target-stop ratchet, or intent-aware action have improved mark to
  market versus simply holding to the last observed production artifact?

No production code, prompt, sizing, entry, LLM, news, or canonical backtest
policy is changed.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260513-008"
EXPERIMENT_SLUG = "legacy_target_lifecycle_replay"
SOURCE_EXPERIMENT_ID = "exp-20260513-005"

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
OPERATOR_POSITIONS_PATH = REPO_ROOT / "operator_inputs" / "open_positions.json"
OUTPUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
ARTIFACT_PATH = OUTPUT_DIR / f"{EXPERIMENT_SLUG}.json"
DOC_LOG_PATH = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT_PATH = (
    REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG_PATH = REPO_ROOT / "docs" / "experiment_log.jsonl"

REDUCE_FRACTION = 0.33
MIN_REALIZED_EVENTS_FOR_PROMOTION = 8


CURRENT_ACCEPTED_BASELINE = {
    "late_strong": {
        "expected_value_score": 4.2340,
        "total_pnl": 94086.91,
        "total_return_pct": 0.9409,
        "sharpe_daily": 4.50,
        "max_drawdown_pct": 0.0548,
        "trade_count": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.6689,
        "total_pnl": 61813.40,
        "total_return_pct": 0.6181,
        "sharpe_daily": 2.70,
        "max_drawdown_pct": 0.0941,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3853,
        "total_pnl": 28544.11,
        "total_return_pct": 0.2854,
        "sharpe_daily": 1.35,
        "max_drawdown_pct": 0.0815,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}


TACTICAL_INTENTS = {"tactical_fomo", "event_trade", "swing", "system_trade"}
CORE_INTENTS = {"core_hold", "legacy_unspecified"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_safe(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _round(value: Any, digits: int = 4) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    return round(number, digits)


def _date_from_signal_file(path: Path, payload: dict[str, Any]) -> str:
    if payload.get("asof_date"):
        return str(payload["asof_date"])
    match = re.search(r"trend_signals_(\d{8})\.json$", path.name)
    if not match:
        return path.stem
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _operator_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in ("positions", "observations"):
        for row in payload.get(section) or []:
            ticker = row.get("ticker")
            if ticker:
                rows.append({**row, "_operator_section": section})
    return rows


def _position_intent(row: dict[str, Any] | None) -> str:
    if not row:
        return "unknown"
    opened_by = str(row.get("opened_by_strategy") or "").lower()
    direction = str(row.get("direction") or "").lower()
    notes = str(row.get("risk_notes") or "").lower()
    blob = " ".join([opened_by, direction, notes])
    if "fomo" in blob:
        return "tactical_fomo"
    if "swing" in blob:
        return "swing"
    if "event" in blob or "earnings" in blob:
        return "event_trade"
    if "core" in blob:
        return "core_hold"
    if "breakout" in blob or "trend" in blob:
        return "system_trade"
    if opened_by == "legacy":
        return "legacy_unspecified"
    return "unknown"


def _rule_names(position_context: dict[str, Any]) -> list[str]:
    exit_signals = position_context.get("exit_signals") or {}
    return [
        str(rule.get("rule"))
        for rule in exit_signals.get("triggered_rules") or []
        if isinstance(rule, dict) and rule.get("rule")
    ]


def _load_timelines() -> dict[str, list[dict[str, Any]]]:
    operator_payload = _load_json(OPERATOR_POSITIONS_PATH)
    operator_by_ticker = {
        str(row["ticker"]): row
        for row in _operator_rows(operator_payload)
    }
    timelines: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(DATA_DIR.glob("trend_signals_*.json")):
        try:
            payload = _load_json(path)
        except Exception:
            continue
        date = _date_from_signal_file(path, payload)
        signals = payload.get("signals") or {}
        if not isinstance(signals, dict):
            continue
        for ticker, signal in signals.items():
            if not isinstance(signal, dict):
                continue
            position_context = signal.get("position")
            if not isinstance(position_context, dict):
                continue
            close = _to_float(signal.get("close"))
            if close is None:
                continue
            exit_levels = position_context.get("exit_levels") or {}
            signal_target = _to_float(exit_levels.get("signal_target_price"))
            operator_row = operator_by_ticker.get(str(ticker))
            operator_target = _to_float((operator_row or {}).get("target_price"))
            target = signal_target if signal_target is not None else operator_target
            daily_high = _to_float(position_context.get("daily_high")) or _to_float(signal.get("daily_high"))
            target_probe = daily_high if daily_high is not None else close
            rule_names = _rule_names(position_context)
            baseline_signal_target = "SIGNAL_TARGET" in rule_names
            legacy_basis = bool(position_context.get("legacy_basis"))
            target_reached = target is not None and target_probe is not None and target_probe >= target
            hard_stop = _to_float(exit_levels.get("hard_stop_price"))
            atr_stop = _to_float(exit_levels.get("atr_stop_price"))
            stop_ratchet = max(
                [value for value in (target, atr_stop, hard_stop) if value is not None],
                default=None,
            )
            row = {
                "date": date,
                "source_file": str(path.relative_to(REPO_ROOT)),
                "ticker": str(ticker),
                "close": close,
                "daily_high": daily_high,
                "target_probe": target_probe,
                "target_price": target,
                "target_reached": target_reached,
                "legacy_basis": legacy_basis,
                "baseline_triggered_rules": rule_names,
                "baseline_signal_target_triggered": baseline_signal_target,
                "silent_suppressed": (
                    target_reached
                    and legacy_basis
                    and not baseline_signal_target
                    and len(rule_names) == 0
                ),
                "all_suppressed": target_reached and legacy_basis and not baseline_signal_target,
                "shares": _to_float(position_context.get("shares")),
                "avg_cost": _to_float(position_context.get("avg_cost")),
                "unrealized_pnl_pct": _to_float(position_context.get("unrealized_pnl_pct")),
                "intent": _position_intent(operator_row),
                "opened_by_strategy": (operator_row or {}).get("opened_by_strategy"),
                "risk_notes": (operator_row or {}).get("risk_notes"),
                "stop_ratchet_price": stop_ratchet,
                "exit_levels": {
                    "hard_stop_price": hard_stop,
                    "atr_stop_price": atr_stop,
                    "signal_target_price": signal_target,
                },
            }
            timelines.setdefault(str(ticker), []).append(row)
    for rows in timelines.values():
        rows.sort(key=lambda row: row["date"])
    return timelines


def _first_trigger_index(rows: list[dict[str, Any]], scope: str) -> int | None:
    key = f"{scope}_suppressed"
    for idx, row in enumerate(rows):
        if row.get(key):
            return idx
    return None


def _next_index(rows: list[dict[str, Any]], idx: int) -> int | None:
    nxt = idx + 1
    return nxt if nxt < len(rows) else None


def _stop_exit_index(rows: list[dict[str, Any]], start_idx: int, stop_price: float | None) -> int | None:
    if stop_price is None:
        return None
    for idx in range(start_idx + 1, len(rows)):
        if rows[idx]["close"] <= stop_price:
            return idx
    return None


def _base_event(
    ticker: str,
    rows: list[dict[str, Any]],
    trigger_idx: int,
) -> dict[str, Any] | None:
    trigger = rows[trigger_idx]
    final = rows[-1]
    shares = _to_float(trigger.get("shares"))
    if shares is None or shares <= 0:
        return None
    fill_idx = _next_index(rows, trigger_idx)
    fill = rows[fill_idx] if fill_idx is not None else None
    target = _to_float(trigger.get("target_price"))
    target_vs_trigger_close_pct = (
        (target - trigger["close"]) / trigger["close"]
        if target is not None and trigger["close"] > 0
        else None
    )
    target_vs_fill_close_pct = (
        (target - fill["close"]) / fill["close"]
        if target is not None and fill is not None and fill["close"] > 0
        else None
    )
    return {
        "ticker": ticker,
        "trigger_idx": trigger_idx,
        "trigger_date": trigger["date"],
        "trigger_close": _round(trigger["close"]),
        "trigger_daily_high": _round(trigger.get("daily_high")),
        "target_price": _round(trigger.get("target_price")),
        "target_probe": _round(trigger.get("target_probe")),
        "target_vs_trigger_close_pct": _round(target_vs_trigger_close_pct, 6),
        "target_vs_fill_close_pct": _round(target_vs_fill_close_pct, 6),
        "stale_target_10pct_below_trigger": (
            target_vs_trigger_close_pct is not None and target_vs_trigger_close_pct <= -0.10
        ),
        "baseline_triggered_rules": trigger["baseline_triggered_rules"],
        "intent": trigger["intent"],
        "shares": shares,
        "avg_cost": _round(trigger.get("avg_cost")),
        "unrealized_pnl_pct": _round(trigger.get("unrealized_pnl_pct")),
        "stop_ratchet_price": _round(trigger.get("stop_ratchet_price")),
        "fill_available": fill is not None,
        "fill_date": fill["date"] if fill else None,
        "fill_close": _round(fill["close"]) if fill else None,
        "final_date": final["date"],
        "final_close": _round(final["close"]),
        "source_file": trigger["source_file"],
    }


def _full_exit_event(ticker: str, rows: list[dict[str, Any]], trigger_idx: int) -> dict[str, Any] | None:
    event = _base_event(ticker, rows, trigger_idx)
    if event is None:
        return None
    fill_idx = _next_index(rows, trigger_idx)
    if fill_idx is None:
        event.update(
            {
                "status": "pending_no_next_observed_close",
                "variant_action": "EXIT_FULL",
                "delta_vs_hold_usd": 0.0,
                "realized": False,
            }
        )
        return event
    fill = rows[fill_idx]
    final = rows[-1]
    delta = event["shares"] * (fill["close"] - final["close"])
    event.update(
        {
            "status": "realized_proxy",
            "variant_action": "EXIT_FULL",
            "exit_date": fill["date"],
            "exit_price": _round(fill["close"]),
            "delta_vs_hold_usd": round(delta, 2),
            "realized": True,
        }
    )
    return event


def _ratchet_event(ticker: str, rows: list[dict[str, Any]], trigger_idx: int) -> dict[str, Any] | None:
    event = _base_event(ticker, rows, trigger_idx)
    if event is None:
        return None
    trigger = rows[trigger_idx]
    final = rows[-1]
    stop_price = _to_float(trigger.get("stop_ratchet_price"))
    stop_idx = _stop_exit_index(rows, trigger_idx, stop_price)
    if stop_idx is None:
        event.update(
            {
                "status": "held_to_final_no_observed_stop",
                "variant_action": "RATCHET_STOP_HOLD",
                "exit_date": None,
                "exit_price": None,
                "delta_vs_hold_usd": 0.0,
                "realized": False,
            }
        )
        return event
    fill = rows[stop_idx]
    delta = event["shares"] * (fill["close"] - final["close"])
    event.update(
        {
            "status": "observed_stop_exit",
            "variant_action": "RATCHET_STOP_HOLD",
            "exit_date": fill["date"],
            "exit_price": _round(fill["close"]),
            "delta_vs_hold_usd": round(delta, 2),
            "realized": True,
        }
    )
    return event


def _intent_aware_event(ticker: str, rows: list[dict[str, Any]], trigger_idx: int) -> dict[str, Any] | None:
    trigger = rows[trigger_idx]
    if trigger["intent"] in TACTICAL_INTENTS:
        event = _full_exit_event(ticker, rows, trigger_idx)
        if event is not None:
            event["variant_action"] = "INTENT_AWARE_EXIT_FULL"
        return event
    if trigger["intent"] in CORE_INTENTS:
        event = _base_event(ticker, rows, trigger_idx)
        if event is None:
            return None
        fill_idx = _next_index(rows, trigger_idx)
        final = rows[-1]
        reduce_delta = 0.0
        stop_delta = 0.0
        realized = False
        exit_parts: list[dict[str, Any]] = []
        remaining_shares = event["shares"]
        if fill_idx is not None:
            fill = rows[fill_idx]
            reduce_shares = event["shares"] * REDUCE_FRACTION
            remaining_shares = event["shares"] - reduce_shares
            reduce_delta = reduce_shares * (fill["close"] - final["close"])
            realized = True
            exit_parts.append(
                {
                    "action": "REDUCE",
                    "fraction": REDUCE_FRACTION,
                    "date": fill["date"],
                    "price": _round(fill["close"]),
                    "delta_vs_hold_usd": round(reduce_delta, 2),
                }
            )
        stop_idx = _stop_exit_index(rows, trigger_idx, _to_float(trigger.get("stop_ratchet_price")))
        if stop_idx is not None:
            fill = rows[stop_idx]
            stop_delta = remaining_shares * (fill["close"] - final["close"])
            realized = True
            exit_parts.append(
                {
                    "action": "RATCHET_STOP_REMAINDER",
                    "date": fill["date"],
                    "price": _round(fill["close"]),
                    "delta_vs_hold_usd": round(stop_delta, 2),
                }
            )
        event.update(
            {
                "status": "realized_proxy" if realized else "held_to_final_no_observed_stop",
                "variant_action": "INTENT_AWARE_REDUCE_AND_RAISE_STOP",
                "exit_parts": exit_parts,
                "delta_vs_hold_usd": round(reduce_delta + stop_delta, 2),
                "realized": realized,
            }
        )
        return event
    return _ratchet_event(ticker, rows, trigger_idx)


def _aggregate_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    total_delta = round(sum(_to_float(event.get("delta_vs_hold_usd")) or 0.0 for event in events), 2)
    realized = [event for event in events if event.get("realized")]
    positive = [event for event in events if (_to_float(event.get("delta_vs_hold_usd")) or 0.0) > 0]
    negative = [event for event in events if (_to_float(event.get("delta_vs_hold_usd")) or 0.0) < 0]
    contribution_by_ticker = Counter()
    for event in events:
        contribution_by_ticker[event["ticker"]] += _to_float(event.get("delta_vs_hold_usd")) or 0.0
    worst = min(events, key=lambda event: _to_float(event.get("delta_vs_hold_usd")) or 0.0, default=None)
    best = max(events, key=lambda event: _to_float(event.get("delta_vs_hold_usd")) or 0.0, default=None)
    return {
        "event_count": len(events),
        "realized_event_count": len(realized),
        "pending_event_count": len(events) - len(realized),
        "positive_delta_count": len(positive),
        "negative_delta_count": len(negative),
        "total_delta_vs_hold_usd": total_delta,
        "avg_delta_vs_hold_usd": round(total_delta / len(events), 2) if events else 0.0,
        "tickers": sorted({event["ticker"] for event in events}),
        "contribution_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(contribution_by_ticker.items())
        },
        "best_event": best,
        "worst_event": worst,
    }


def _run_variant(timelines: dict[str, list[dict[str, Any]]], scope: str, policy: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for ticker, rows in sorted(timelines.items()):
        trigger_idx = _first_trigger_index(rows, scope)
        if trigger_idx is None:
            continue
        if policy == "full_exit_next_observed_close":
            event = _full_exit_event(ticker, rows, trigger_idx)
        elif policy == "target_stop_ratchet":
            event = _ratchet_event(ticker, rows, trigger_idx)
        elif policy == "intent_aware_exit_or_ratchet":
            event = _intent_aware_event(ticker, rows, trigger_idx)
        else:  # pragma: no cover - guarded by caller.
            raise ValueError(policy)
        if event is None:
            skipped.append({"ticker": ticker, "trigger_idx": trigger_idx, "reason": "missing_shares"})
        else:
            events.append(event)
    aggregate = _aggregate_events(events)
    return {
        "scope": scope,
        "policy": policy,
        "aggregate": aggregate,
        "events": events,
        "skipped": skipped,
        "gate": {
            "sample_guard_passed": aggregate["realized_event_count"] >= MIN_REALIZED_EVENTS_FOR_PROMOTION,
            "positive_delta": aggregate["total_delta_vs_hold_usd"] > 0,
            "passed_for_promotion": False,
            "reason": (
                "production-position replay is a measurement repair; promotion still requires shared policy tests and live/forward evidence"
            ),
        },
    }


def run() -> dict[str, Any]:
    timelines = _load_timelines()
    policies = (
        "full_exit_next_observed_close",
        "target_stop_ratchet",
        "intent_aware_exit_or_ratchet",
    )
    scopes = ("silent", "all")
    variants: dict[str, Any] = {}
    for scope in scopes:
        for policy in policies:
            key = f"{scope}_{policy}"
            variants[key] = _run_variant(timelines, scope, policy)

    best_name, best_variant = max(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["total_delta_vs_hold_usd"],
            item[1]["aggregate"]["realized_event_count"],
        ),
    )
    full_exit_primary = variants["silent_full_exit_next_observed_close"]
    ratchet_primary = variants["silent_target_stop_ratchet"]
    intent_primary = variants["silent_intent_aware_exit_or_ratchet"]
    decision = "rejected_no_full_exit_promotion_target_ratchet_preferred_for_next_policy_test"
    interpretation = (
        "Full EXIT on first silent legacy-suppressed target was negative versus holding on the saved production-position replay. "
        "The target-stop ratchet variant avoided that opportunity cost but was mostly inert over the short saved sample. "
        "This supports fixing target visibility, but not promoting blunt full exits for legacy winners."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "measurement_repair",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "A legacy-basis explicit target override may improve live exit behavior, but the action after surfacing the target should be tested: full exit may truncate high-beta winners, while a stop ratchet may preserve upside."
        ),
        "change_type": "production_position_exit_replay",
        "changed_variable": "legacy_explicit_target_lifecycle_policy",
        "single_causal_variable": "action taken after explicit target is reached while legacy_basis suppresses SIGNAL_TARGET",
        "parameters": {
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "data_source": "saved data/trend_signals_*.json production artifacts",
            "primary_scope": "silent_suppressed = explicit target reached, legacy_basis true, no baseline triggered rules",
            "diagnostic_scope": "all_suppressed = explicit target reached, legacy_basis true, baseline has no SIGNAL_TARGET",
            "fill_proxy": "next observed saved close after trigger; pending if no later artifact exists",
            "baseline_proxy": "hold same shares to last observed saved close for that ticker",
            "tested_policies": list(policies),
            "reduce_fraction_for_core_intent": REDUCE_FRACTION,
            "locked_variables": [
                "entries",
                "sizing",
                "portfolio heat",
                "LLM",
                "news",
                "canonical backtester target exits",
                "avg_cost profit ladders",
                "position universe",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "exit / measurement repair: legacy explicit-target visibility may improve held-position lifecycle",
            "2_history_check": {
                "exp-20260429-032": "rejected bare SIGNAL_TARGET 33% partial-reduce replay; this experiment does not retest that backtester path.",
                "exp-20260513-005": "confirmed observed production shadow suppression of explicit targets by legacy_basis.",
            },
            "3_single_causal_variable": "legacy_explicit_target_lifecycle_policy",
            "4_acceptance_standard": "measurement replay must show positive delta with enough realized events before shared policy promotion; canonical core metrics remain unchanged.",
            "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_008_legacy_target_lifecycle_replay.py",
        },
        "backtest_protocol": {
            "type": "production_position_replay_not_canonical_core_backtest",
            "reason_canonical_core_backtest_not_applicable": (
                "BacktestEngine simulated positions already execute target_price; the bug exists in production held-position advisory context."
            ),
            "canonical_baseline_metrics_unchanged": CURRENT_ACCEPTED_BASELINE,
        },
        "before_metrics": {
            "baseline_policy": "hold when legacy_basis suppresses SIGNAL_TARGET",
            "canonical_core": CURRENT_ACCEPTED_BASELINE,
        },
        "after_metrics": {
            "best_variant": best_name,
            "best_variant_aggregate": best_variant["aggregate"],
            "canonical_core": CURRENT_ACCEPTED_BASELINE,
        },
        "delta_metrics": {
            "canonical_backtest_metrics_changed": False,
            "silent_full_exit_delta_vs_hold_usd": full_exit_primary["aggregate"]["total_delta_vs_hold_usd"],
            "silent_ratchet_delta_vs_hold_usd": ratchet_primary["aggregate"]["total_delta_vs_hold_usd"],
            "silent_intent_aware_delta_vs_hold_usd": intent_primary["aggregate"]["total_delta_vs_hold_usd"],
            "best_variant_delta_vs_hold_usd": best_variant["aggregate"]["total_delta_vs_hold_usd"],
        },
        "variants": variants,
        "best_variant": best_name,
        "interpretation": interpretation,
        "gate": {
            "passed_for_shared_policy_promotion": False,
            "reason": (
                "Do not promote full exit: primary silent full-exit replay is negative. "
                "Use this as evidence for a narrower shared target-visibility + ratchet/review policy test."
            ),
            "primary_full_exit": full_exit_primary["aggregate"],
            "primary_ratchet": ratchet_primary["aggregate"],
            "primary_intent_aware": intent_primary["aggregate"],
        },
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
        },
        "rejection_reason": "Blunt full-exit policy is negative on primary silent production-position replay; ratchet is safer but needs shared-policy test and forward evidence.",
        "next_retry_requires": [
            "Implement only target visibility or target stop-ratchet as a shared policy candidate, not a full-exit override.",
            "Add tests proving legacy_basis still suppresses avg_cost profit ladders but not explicit target visibility.",
            "Treat TSLA 2026-05-11 as pending: no later saved artifact exists to score whether exiting at that alert would help.",
        ],
        "related_files": [
            "quant/experiments/exp_20260513_008_legacy_target_lifecycle_replay.py",
            "quant/experiments/exp_20260513_005_legacy_explicit_target_exit_shadow.py",
            "data/experiments/exp-20260513-008/legacy_target_lifecycle_replay.json",
            "docs/experiments/logs/exp-20260513-008.json",
            "docs/experiments/artifacts/exp-20260513-008_legacy_target_lifecycle_replay.md",
            "docs/experiment_log.jsonl",
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Legacy Target Lifecycle Replay",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        payload["interpretation"],
        "",
        "## Variants",
        "",
        "| Variant | Scope | Policy | Events | Realized | dUSD vs Hold | Tickers |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for name, variant in payload["variants"].items():
        agg = variant["aggregate"]
        lines.append(
            "| {name} | {scope} | {policy} | {events} | {realized} | ${delta:+,.2f} | {tickers} |".format(
                name=name,
                scope=variant["scope"],
                policy=variant["policy"],
                events=agg["event_count"],
                realized=agg["realized_event_count"],
                delta=agg["total_delta_vs_hold_usd"],
                tickers=", ".join(agg["tickers"]),
            )
        )
    lines.extend(
        [
            "",
            "## Primary Silent Events",
            "",
            "| Variant | Ticker | Trigger | Fill | Final | Action | dUSD vs Hold |",
            "|---|---|---|---|---|---|---:|",
        ]
    )
    for variant_name in (
        "silent_full_exit_next_observed_close",
        "silent_target_stop_ratchet",
        "silent_intent_aware_exit_or_ratchet",
    ):
        for event in payload["variants"][variant_name]["events"]:
            lines.append(
                "| {variant} | {ticker} | {trigger} | {fill} | {final} | {action} | ${delta:+,.2f} |".format(
                    variant=variant_name,
                    ticker=event["ticker"],
                    trigger=event["trigger_date"],
                    fill=event.get("fill_date") or event.get("exit_date") or "n/a",
                    final=event["final_date"],
                    action=event.get("variant_action"),
                    delta=event.get("delta_vs_hold_usd") or 0.0,
                )
            )
    return "\n".join(lines) + "\n"


def persist(payload: dict[str, Any]) -> None:
    _write_json(ARTIFACT_PATH, payload)
    _write_json(DOC_LOG_PATH, payload)
    DOC_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT_PATH.write_text(_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_PATH, payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "best_variant": result["best_variant"],
                "silent_full_exit_delta_vs_hold_usd": result["delta_metrics"]["silent_full_exit_delta_vs_hold_usd"],
                "silent_ratchet_delta_vs_hold_usd": result["delta_metrics"]["silent_ratchet_delta_vs_hold_usd"],
                "silent_intent_aware_delta_vs_hold_usd": result["delta_metrics"]["silent_intent_aware_delta_vs_hold_usd"],
                "primary_full_exit": result["gate"]["primary_full_exit"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
