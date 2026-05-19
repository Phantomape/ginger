"""exp-20260513-005: legacy explicit-target exit shadow audit.

Measurement repair / exit-policy attribution.  This experiment changes no
production strategy code.  It audits saved daily production signal artifacts to
measure a narrow parity defect: explicit ``target_price`` can be present and
reached, while ``legacy_basis=True`` suppresses the ``SIGNAL_TARGET`` advisory.

This intentionally does *not* retry the rejected exp-20260429-032 partial-trim
backtest.  The causal variable under study is only whether explicit targets
should be allowed to surface through the legacy-basis guard.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260513-005"
EXPERIMENT_SLUG = "legacy_explicit_target_exit_shadow"

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
OPERATOR_POSITIONS_PATH = REPO_ROOT / "operator_inputs" / "open_positions.json"
OUTPUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
ARTIFACT_PATH = OUTPUT_DIR / f"{EXPERIMENT_SLUG}.json"
DOC_LOG_PATH = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT_PATH = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG_PATH = REPO_ROOT / "docs" / "experiment_log.jsonl"

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
            if not ticker:
                continue
            rows.append({**row, "_operator_section": section})
    return rows


def _position_intent(row: dict[str, Any]) -> str:
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


def _intent_aware_action(intent: str) -> str:
    if intent in {"tactical_fomo", "event_trade", "swing", "system_trade"}:
        return "EXIT_FULL"
    if intent in {"core_hold", "legacy_unspecified"}:
        return "REDUCE_AND_RAISE_STOP"
    return "REVIEW"


def _rule_names(position_context: dict[str, Any]) -> list[str]:
    exit_signals = position_context.get("exit_signals") or {}
    return [
        str(rule.get("rule"))
        for rule in exit_signals.get("triggered_rules") or []
        if isinstance(rule, dict) and rule.get("rule")
    ]


def _build_rows() -> dict[str, Any]:
    operator_payload = _load_json(OPERATOR_POSITIONS_PATH)
    operator_rows = _operator_rows(operator_payload)
    operator_by_ticker = {str(row["ticker"]): row for row in operator_rows}

    signal_files = sorted(DATA_DIR.glob("trend_signals_*.json"))
    observed_rows: list[dict[str, Any]] = []
    missing_context_rows: list[dict[str, Any]] = []
    suppressed_rows: list[dict[str, Any]] = []
    baseline_signal_target_rows: list[dict[str, Any]] = []
    explicit_target_reached_rows: list[dict[str, Any]] = []

    for path in signal_files:
        try:
            payload = _load_json(path)
        except Exception as exc:  # pragma: no cover - defensive audit row.
            missing_context_rows.append(
                {"date": path.name, "ticker": "?", "reason": f"unreadable_signal_file:{exc}"}
            )
            continue
        date = _date_from_signal_file(path, payload)
        signals = payload.get("signals") or {}
        if not isinstance(signals, dict):
            continue
        for ticker, operator_row in operator_by_ticker.items():
            signal = signals.get(ticker)
            if not isinstance(signal, dict):
                missing_context_rows.append(
                    {
                        "date": date,
                        "ticker": ticker,
                        "operator_section": operator_row.get("_operator_section"),
                        "reason": "ticker_not_in_trend_signals",
                    }
                )
                continue
            position_context = signal.get("position")
            if not isinstance(position_context, dict):
                missing_context_rows.append(
                    {
                        "date": date,
                        "ticker": ticker,
                        "operator_section": operator_row.get("_operator_section"),
                        "reason": "trend_signal_has_no_position_context",
                    }
                )
                continue

            exit_levels = position_context.get("exit_levels") or {}
            signal_target = _to_float(exit_levels.get("signal_target_price"))
            operator_target = _to_float(operator_row.get("target_price"))
            target = signal_target if signal_target is not None else operator_target
            close = _to_float(signal.get("close"))
            daily_high = _to_float(position_context.get("daily_high")) or _to_float(signal.get("daily_high"))
            target_probe = daily_high if daily_high is not None else close
            target_source = "daily_high" if daily_high is not None else "close_fallback"
            target_reached = (
                target is not None
                and target_probe is not None
                and target_probe >= target
            )
            rule_names = _rule_names(position_context)
            baseline_has_signal_target = "SIGNAL_TARGET" in rule_names
            legacy_basis = bool(position_context.get("legacy_basis"))
            intent = _position_intent(operator_row)
            current_price = close if close is not None else _to_float(signal.get("current_price"))
            atr_stop = _to_float(exit_levels.get("atr_stop_price"))
            stop_raise_candidate = max(
                [value for value in (target, atr_stop) if value is not None],
                default=None,
            )

            row = {
                "date": date,
                "source_file": str(path.relative_to(REPO_ROOT)),
                "ticker": ticker,
                "operator_section": operator_row.get("_operator_section"),
                "opened_by_strategy": operator_row.get("opened_by_strategy"),
                "direction": operator_row.get("direction"),
                "intent": intent,
                "shares": operator_row.get("shares"),
                "avg_cost": _round(operator_row.get("avg_cost")),
                "entry_date": operator_row.get("entry_date"),
                "operator_target_price": _round(operator_target),
                "signal_target_price": _round(signal_target),
                "target_price_used": _round(target),
                "current_price": _round(current_price),
                "daily_high": _round(daily_high),
                "target_probe": _round(target_probe),
                "target_source": target_source,
                "target_reached": target_reached,
                "legacy_basis": legacy_basis,
                "unrealized_pnl_pct": _round(position_context.get("unrealized_pnl_pct")),
                "baseline_triggered_rules": rule_names,
                "baseline_signal_target_triggered": baseline_has_signal_target,
                "suppressed_by_legacy_basis": (
                    target_reached and legacy_basis and not baseline_has_signal_target
                ),
                "variant_target_exit_action": "EXIT_FULL" if target_reached else "NONE",
                "variant_intent_aware_action": _intent_aware_action(intent) if target_reached else "NONE",
                "variant_stop_raise_candidate": _round(stop_raise_candidate),
                "atr_stop_price": _round(atr_stop),
                "existing_exit_levels": {
                    "hard_stop_price": _round(exit_levels.get("hard_stop_price")),
                    "atr_stop_price": _round(exit_levels.get("atr_stop_price")),
                    "profit_target_price": _round(exit_levels.get("profit_target_price")),
                    "signal_target_price": _round(exit_levels.get("signal_target_price")),
                },
            }
            observed_rows.append(row)
            if target_reached:
                explicit_target_reached_rows.append(row)
            if baseline_has_signal_target:
                baseline_signal_target_rows.append(row)
            if row["suppressed_by_legacy_basis"]:
                suppressed_rows.append(row)

    return {
        "operator_position_rows": operator_rows,
        "signal_files": [str(path.relative_to(REPO_ROOT)) for path in signal_files],
        "observed_rows": observed_rows,
        "explicit_target_reached_rows": explicit_target_reached_rows,
        "baseline_signal_target_rows": baseline_signal_target_rows,
        "suppressed_rows": suppressed_rows,
        "missing_context_rows": missing_context_rows,
    }


def _summarize(rows_payload: dict[str, Any]) -> dict[str, Any]:
    observed_rows = rows_payload["observed_rows"]
    reached = rows_payload["explicit_target_reached_rows"]
    suppressed = rows_payload["suppressed_rows"]
    baseline_signal_target = rows_payload["baseline_signal_target_rows"]
    missing = rows_payload["missing_context_rows"]

    by_ticker: dict[str, dict[str, Any]] = {}
    for ticker in sorted({row["ticker"] for row in observed_rows + missing}):
        ticker_rows = [row for row in observed_rows if row["ticker"] == ticker]
        ticker_missing = [row for row in missing if row["ticker"] == ticker]
        ticker_suppressed = [row for row in suppressed if row["ticker"] == ticker]
        by_ticker[ticker] = {
            "position_context_rows": len(ticker_rows),
            "missing_context_rows": len(ticker_missing),
            "explicit_target_reached_rows": sum(1 for row in ticker_rows if row["target_reached"]),
            "baseline_signal_target_rows": sum(
                1 for row in ticker_rows if row["baseline_signal_target_triggered"]
            ),
            "suppressed_by_legacy_basis_rows": len(ticker_suppressed),
            "latest_suppressed_row": ticker_suppressed[-1] if ticker_suppressed else None,
            "missing_reasons": dict(Counter(row["reason"] for row in ticker_missing)),
        }

    by_intent = defaultdict(lambda: {"rows": 0, "suppressed": 0})
    for row in observed_rows:
        by_intent[row["intent"]]["rows"] += 1
        if row["suppressed_by_legacy_basis"]:
            by_intent[row["intent"]]["suppressed"] += 1

    return {
        "signal_file_count": len(rows_payload["signal_files"]),
        "operator_rows_total": len(rows_payload["operator_position_rows"]),
        "position_context_rows": len(observed_rows),
        "missing_context_rows": len(missing),
        "explicit_target_reached_rows": len(reached),
        "baseline_signal_target_rows": len(baseline_signal_target),
        "suppressed_by_legacy_basis_rows": len(suppressed),
        "suppressed_tickers": sorted({row["ticker"] for row in suppressed}),
        "suppressed_latest_date": max((row["date"] for row in suppressed), default=None),
        "suppressed_by_ticker_counts": dict(Counter(row["ticker"] for row in suppressed)),
        "target_reached_by_ticker_counts": dict(Counter(row["ticker"] for row in reached)),
        "by_ticker": by_ticker,
        "by_intent": dict(by_intent),
    }


def _payload() -> dict[str, Any]:
    rows_payload = _build_rows()
    summary = _summarize(rows_payload)
    measurement_gate_passed = summary["suppressed_by_legacy_basis_rows"] > 0
    decision = (
        "observed_only_measurement_gap_confirmed"
        if measurement_gate_passed
        else "observed_only_no_legacy_target_suppression_found"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "status": "observed_only",
        "lane": "measurement_repair",
        "hypothesis": (
            "Explicit strategy target_price should remain actionable even when a "
            "position is marked legacy_basis; legacy_basis should suppress only "
            "avg_cost-anchored profit ladders, not an explicit recorded target."
        ),
        "alpha_hypothesis": {
            "category": "exit / measurement_repair",
            "statement": (
                "Some poor live exit outcomes may be caused by explicit targets "
                "being hidden behind the legacy_basis guard rather than by weak "
                "ticker alpha."
            ),
        },
        "historical_experiment_check": {
            "anti_repeat": (
                "Not exp-20260429-032. This run does not convert target_price to a "
                "33% partial reduce in backtest and does not alter canonical exits."
            ),
            "related_failure": (
                "exp-20260429-032 rejected bare SIGNAL_TARGET partial-reduce replay "
                "after EV and PnL regressed in all three windows."
            ),
        },
        "single_causal_variable": "legacy_basis_guard_for_explicit_signal_target",
        "parameters": {
            "baseline_behavior": "evaluate_exit_signals requires not legacy_basis before SIGNAL_TARGET",
            "shadow_variant": "allow explicit signal_target_price to surface despite legacy_basis",
            "locked_variables": [
                "entry rules",
                "sizing",
                "portfolio heat",
                "LLM",
                "news",
                "canonical backtester target fills",
                "avg_cost profit ladders",
                "trailing-stop advisory disabled state",
            ],
            "treatment_definition": (
                "operator position has target_price; saved daily trend signal has "
                "daily_high or close >= target; position_context.legacy_basis is true; "
                "current baseline exit_signals do not include SIGNAL_TARGET"
            ),
        },
        "gate": {
            "type": "observed_only_shadow",
            "passed": measurement_gate_passed,
            "success_condition": "at least one saved production day shows suppressed explicit target",
            "promotion_requirements": [
                "move SIGNAL_TARGET legacy override into shared position_manager policy",
                "keep avg_cost profit ladder disabled for legacy_basis",
                "add focused tests for legacy_basis + explicit target hit",
                "run production parity tests",
                "confirm canonical fixed-window backtest metrics do not move unless a full lifecycle replay is explicitly promoted",
            ],
        },
        "baseline_metrics": CURRENT_ACCEPTED_BASELINE,
        "after_metrics": CURRENT_ACCEPTED_BASELINE,
        "delta_metrics": {
            "canonical_backtest_metrics_changed": False,
            "expected_value_score_delta_sum": 0.0,
            "total_pnl_delta_sum": 0.0,
            "observed_shadow": {
                "suppressed_by_legacy_basis_rows": summary["suppressed_by_legacy_basis_rows"],
                "explicit_target_reached_rows": summary["explicit_target_reached_rows"],
                "baseline_signal_target_rows": summary["baseline_signal_target_rows"],
            },
        },
        "summary": summary,
        "suppressed_rows": rows_payload["suppressed_rows"],
        "explicit_target_reached_rows": rows_payload["explicit_target_reached_rows"],
        "baseline_signal_target_rows": rows_payload["baseline_signal_target_rows"],
        "missing_context_sample": rows_payload["missing_context_rows"][:80],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "observed_only": True,
        },
        "decision": decision,
        "next_retry_requires": [
            "If promoted, implement the narrow shared policy change in position_manager.evaluate_exit_signals.",
            "Do not implement a partial-reduce replay by itself; exp-20260429-032 already rejected that path.",
            "Separate intent-aware action semantics from the legacy guard fix if full EXIT vs REDUCE needs optimization.",
        ],
        "related_files": [
            "quant/position_manager.py",
            "quant/trend_signals.py",
            "operator_inputs/open_positions.json",
            str(ARTIFACT_PATH.relative_to(REPO_ROOT)),
            str(DOC_LOG_PATH.relative_to(REPO_ROOT)),
        ],
    }


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
                existing_payload = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if existing_payload.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} Legacy Explicit Target Exit Shadow",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Single variable: whether `legacy_basis` suppresses an explicit recorded `target_price`.",
        "",
        "## Summary",
        "",
        f"- Signal files scanned: {summary['signal_file_count']}",
        f"- Position context rows: {summary['position_context_rows']}",
        f"- Explicit target reached rows: {summary['explicit_target_reached_rows']}",
        f"- Baseline SIGNAL_TARGET rows: {summary['baseline_signal_target_rows']}",
        f"- Suppressed by legacy_basis rows: {summary['suppressed_by_legacy_basis_rows']}",
        f"- Suppressed tickers: {', '.join(summary['suppressed_tickers']) or 'none'}",
        "",
        "## Suppressed Rows",
        "",
        "| Date | Ticker | Intent | Price | High | Target | Current Rules | Shadow Action |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for row in payload["suppressed_rows"]:
        rules = ", ".join(row["baseline_triggered_rules"]) or "none"
        lines.append(
            "| {date} | {ticker} | {intent} | {price} | {high} | {target} | {rules} | {action} |".format(
                date=row["date"],
                ticker=row["ticker"],
                intent=row["intent"],
                price=row["current_price"],
                high=row["daily_high"],
                target=row["target_price_used"],
                rules=rules,
                action=row["variant_intent_aware_action"],
            )
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "This is not the rejected `exp-20260429-032` target partial-reduce replay. "
            "No production policy, canonical backtest exit, entry, sizing, LLM, or news behavior changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = _payload()
    _write_json(ARTIFACT_PATH, payload)
    _write_json(DOC_LOG_PATH, payload)
    DOC_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT_PATH.write_text(_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_PATH, payload)
    print(json.dumps(_safe(payload["summary"]), ensure_ascii=False, indent=2, sort_keys=True))
    print(f"wrote {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
