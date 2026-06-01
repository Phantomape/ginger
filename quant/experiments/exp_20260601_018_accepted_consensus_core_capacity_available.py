"""exp-20260601-018: accepted consensus core-capacity-available gate.

Lane: alpha_search.
Single causal variable:
    accepted_free_data_consensus_core_capacity_available_gate_v1.

This tests whether the accepted free-data cross-source consensus paper queue
has cleaner activation value when admitted only on signal dates where the core
replay still has unused position capacity after baseline core entries. It is a
capacity/replacement-value discriminator, not a source-count, notional, hold,
liquidity, or ticker expansion retune.

No JavaScript was used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.constants import MAX_POSITIONS  # noqa: E402
from quant.experiments import (  # noqa: E402
    exp_20260531_030_accepted_free_data_cross_source_consensus as source,
)


EXPERIMENT_ID = "exp-20260601-018"
STEM = "accepted_consensus_core_capacity_available"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_capacity_gate"
CHANGED_VARIABLE = "accepted_free_data_consensus_core_capacity_available_gate_v1"
RULE_VERSION = CHANGED_VARIABLE

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_018_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"exp_20260601_018_{STEM}_before.json"
AFTER_JSON = OUT_DIR / f"exp_20260601_018_{STEM}_after.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

PRODUCTION_IMPACT = {
    "replay_only": True,
    "default_off_paper_only": True,
    "shared_policy_changed": False,
    "run_adapter_changed": False,
    "backtester_adapter_changed": False,
    "parity_test_added": False,
    "trade_enabled": False,
    "alters_orders": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
}

DOCS_ACCEPTED_BASELINE = {
    "late_strong": {"expected_value_score": 5.1628, "total_pnl": 117_072.92},
    "mid_weak": {"expected_value_score": 2.1402, "total_pnl": 78_110.11},
    "old_thin": {"expected_value_score": 0.5911, "total_pnl": 39_667.96},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_safe(record), sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                item = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if item.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _core_active_after_close(trades: list[dict[str, Any]], signal_date: str) -> int:
    day = _parse_day(signal_date)
    if day is None:
        return MAX_POSITIONS
    active = 0
    for trade in trades:
        entry = _parse_day(trade.get("entry_date"))
        exit_day = _parse_day(trade.get("exit_date"))
        if entry is None:
            continue
        if entry <= day and (exit_day is None or exit_day > day):
            active += 1
    return active


def _baseline_drift(core_metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    for label, expected in DOCS_ACCEPTED_BASELINE.items():
        actual = core_metrics_by_window.get(label) or {}
        ev_delta = float(actual.get("expected_value_score") or 0.0) - expected[
            "expected_value_score"
        ]
        pnl_delta = float(actual.get("total_pnl") or 0.0) - expected["total_pnl"]
        rows[label] = {
            "docs_expected_value_score": expected["expected_value_score"],
            "current_expected_value_score": actual.get("expected_value_score"),
            "expected_value_score_delta": round(ev_delta, 6),
            "docs_total_pnl": expected["total_pnl"],
            "current_total_pnl": actual.get("total_pnl"),
            "total_pnl_delta": round(pnl_delta, 2),
            "matches_docs_baseline": abs(ev_delta) <= 0.01 and abs(pnl_delta) <= 100.0,
        }
    return {
        "docs_source": "docs/backtesting.md accepted exp-20260517-009 metrics",
        "current_source": "current replay in the same docs/backtesting.md windows",
        "matches_all_windows": all(row["matches_docs_baseline"] for row in rows.values()),
        "rows": rows,
    }


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in results)
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in results)
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in results)
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in results)
    return {
        "before": {
            "expected_value_score": round(before_ev, 6),
            "total_pnl": round(before_pnl, 2),
            "strategy_total_pnl": round(before_pnl, 2),
        },
        "after": {
            "expected_value_score": round(after_ev, 6),
            "total_pnl": round(after_pnl, 2),
            "strategy_total_pnl": round(after_pnl, 2),
        },
        "comparison": {
            "expected_value_score_delta": round(after_ev - before_ev, 6),
            "expected_value_score_delta_pct": round((after_ev - before_ev) / before_ev, 6)
            if before_ev
            else None,
            "strategy_total_pnl_delta": round(after_pnl - before_pnl, 2),
            "total_pnl_delta": round(after_pnl - before_pnl, 2),
            "strategy_total_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
            if before_pnl
            else None,
        },
    }


def _target_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        pnl = float(trade.get("pnl") or 0.0)
        by_ticker_count[ticker] += 1
        by_ticker_pnl[ticker] += pnl
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        max(positive.values()) / positive_total if positive_total > 0 and positive else None
    )
    positive_hhi = (
        sum((pnl / positive_total) ** 2 for pnl in positive.values())
        if positive_total > 0 and positive
        else None
    )
    ticker_rows = []
    for ticker, pnl in sorted(by_ticker_pnl.items()):
        ticker_rows.append(
            {
                "ticker": ticker,
                "trade_count": by_ticker_count[ticker],
                "paper_pnl_usd": round(pnl, 2),
                "positive_pnl_usd": round(max(pnl, 0.0), 2),
                "positive_pnl_share": round(pnl / positive_total, 6)
                if pnl > 0 and positive_total > 0
                else None,
            }
        )
    ticker_rows.sort(
        key=lambda row: (
            -(row["positive_pnl_usd"] or 0.0),
            -abs(row["paper_pnl_usd"] or 0.0),
            row["ticker"],
        )
    )
    return {
        "target_trade_count": len(trades),
        "target_trade_pnl_usd": round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
        "positive_pnl_total_usd": round(positive_total, 2),
        "max_single_positive_share": round(max_positive_share, 6)
        if max_positive_share is not None
        else None,
        "positive_pnl_hhi": round(positive_hhi, 6) if positive_hhi is not None else None,
        "trades_by_window": {label: len(rows) for label, rows in target_trades_by_window.items()},
        "pnl_by_window": {
            label: round(sum(float(row.get("pnl") or 0.0) for row in rows), 2)
            for label, rows in target_trades_by_window.items()
        },
        "ticker_rows": ticker_rows,
    }


def _trade_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("signal_date") or row.get("date") or ""), str(row.get("ticker") or ""))


def _run_windows() -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    source_rows = source._source_rows_by_window()
    baselines = source._load_baselines()
    results: list[dict[str, Any]] = []
    core_metrics_by_window: dict[str, dict[str, Any]] = {}
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}

    for label, cfg in source.base.WINDOWS.items():
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        core_metrics_by_window[label] = before
        baseline_entries = source.base.shadow._baseline_entries(before_result)
        core_trades = [
            row for row in before_result.get("trades") or [] if isinstance(row, dict)
        ]
        snapshot = source.base.shadow._load_snapshot(cfg["snapshot"])
        raw_candidates = source._consensus_candidates_for_window(label, source_rows)

        capacity_candidates: list[dict[str, Any]] = []
        no_core_candidates: list[dict[str, Any]] = []
        rejected_capacity_full: list[dict[str, Any]] = []
        for candidate in raw_candidates:
            signal_date = str(candidate["date"])
            same_day_core_entry_count = len(baseline_entries.get(signal_date, []))
            active_core_after_close = _core_active_after_close(core_trades, signal_date)
            available_core_slots = max(0, MAX_POSITIONS - active_core_after_close)
            annotated = dict(candidate)
            annotated.update(
                {
                    "capacity_gate_rule_version": RULE_VERSION,
                    "capacity_gate": "core_capacity_available_after_close",
                    "same_day_core_entry_count": same_day_core_entry_count,
                    "active_core_positions_after_signal_close": active_core_after_close,
                    "available_core_slots_after_signal_close": available_core_slots,
                    "max_core_positions": MAX_POSITIONS,
                    "rule_version": RULE_VERSION,
                }
            )
            if same_day_core_entry_count == 0:
                no_core_candidates.append(annotated)
            if available_core_slots > 0:
                capacity_candidates.append(annotated)
            else:
                rejected_capacity_full.append(annotated)

        capacity_trades, capacity_diagnostics = source._select_target_trades(
            snapshot,
            capacity_candidates,
        )
        no_core_trades, no_core_diagnostics = source._select_target_trades(
            snapshot,
            no_core_candidates,
        )
        for trade in capacity_trades:
            trade["capacity_gate_rule_version"] = RULE_VERSION
            trade["capacity_gate"] = "core_capacity_available_after_close"

        overlay = source.base._overlay_from_paper_trades(before_result, capacity_trades)
        after = source.base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = source.base.overlay_helper._delta(after, before)
        capacity_keys = {_trade_key(row) for row in capacity_trades}
        no_core_keys = {_trade_key(row) for row in no_core_trades}
        extra_capacity_keys = sorted(capacity_keys - no_core_keys)
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "before": before,
                "after": after,
                "comparison": {
                    "expected_value_score_delta": raw_delta["expected_value_score"],
                    "strategy_total_pnl_delta": raw_delta["total_pnl"],
                    "total_pnl_delta": raw_delta["total_pnl"],
                    "max_drawdown_delta": raw_delta["max_drawdown_pct"],
                    "raw_delta": raw_delta,
                },
                "raw_consensus_candidate_count": len(raw_candidates),
                "capacity_pass_candidate_count": len(capacity_candidates),
                "capacity_full_rejected_candidate_count": len(rejected_capacity_full),
                "no_core_candidate_count": len(no_core_candidates),
                "capacity_target_trade_count": len(capacity_trades),
                "no_core_target_trade_count": len(no_core_trades),
                "extra_capacity_target_trade_count": len(extra_capacity_keys),
                "extra_capacity_target_trade_keys": extra_capacity_keys,
                "capacity_target_trade_pnl_usd": round(
                    sum(float(row.get("pnl") or 0.0) for row in capacity_trades), 2
                ),
                "no_core_target_trade_pnl_usd": round(
                    sum(float(row.get("pnl") or 0.0) for row in no_core_trades), 2
                ),
                "capacity_diagnostics": capacity_diagnostics,
                "no_core_diagnostics": no_core_diagnostics,
            }
        )
        target_trades_by_window[label] = capacity_trades
    return results, core_metrics_by_window, target_trades_by_window


def _judge(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    baseline_drift: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison["expected_value_score_delta"])
    pnl_delta = float(comparison["strategy_total_pnl_delta"])
    ev_windows = [
        row["label"] for row in results if float(row["comparison"]["expected_value_score_delta"]) > 0
    ]
    pnl_windows = [
        row["label"] for row in results if float(row["comparison"]["strategy_total_pnl_delta"]) > 0
    ]
    max_drawdown_delta = max(float(row["comparison"]["max_drawdown_delta"]) for row in results)
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    target_window_count = sum(1 for row in results if int(row["capacity_target_trade_count"]) > 0)
    extra_capacity_target_trade_count = sum(
        int(row["extra_capacity_target_trade_count"]) for row in results
    )
    concentration_passed = (
        target_summary["max_single_positive_share"] is not None
        and target_summary["max_single_positive_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    gates = {
        "aggregate_expected_value_positive": ev_delta > 0,
        "aggregate_pnl_positive": pnl_delta > 0,
        "all_windows_expected_value_improved": len(ev_windows) == len(results),
        "all_windows_pnl_improved": len(pnl_windows) == len(results),
        "target_trade_count_passed": target_summary["target_trade_count"] >= MIN_TARGET_TRADES,
        "target_window_count_passed": target_window_count >= MIN_TARGET_WINDOWS,
        "drawdown_drift_passed": max_drawdown_delta <= MAX_DRAWDOWN_WORSE,
        "survival_floor_passed": min_survival_rate >= 0.05,
        "concentration_guard_passed": concentration_passed,
        "distinct_from_no_core_gate": extra_capacity_target_trade_count > 0,
        "baseline_matches_docs": bool(baseline_drift["matches_all_windows"]),
    }
    alpha_checks_passed = all(value for key, value in gates.items() if key != "baseline_matches_docs")
    retained = alpha_checks_passed and gates["baseline_matches_docs"]
    if retained:
        decision = "accepted_replay_lead_requires_shared_core_capacity_adapter"
        rationale = (
            "The core-capacity-available gate passed the three-window alpha checks and "
            "baseline matched docs. A shared production/backtest adapter would still be required."
        )
    elif alpha_checks_passed:
        decision = "positive_replay_lead_not_promoted_requires_clean_baseline_and_shared_adapter"
        rationale = (
            "The core-capacity-available gate passed alpha checks, but current-code "
            "baseline metrics drift from docs/backtesting.md; no shared behavior is retained."
        )
    else:
        decision = "rejected_accepted_consensus_core_capacity_available_gate"
        rationale = (
            "The core-capacity-available gate did not clear the three-window alpha checks. "
            "No production/shared behavior is retained."
        )
    failed_gates = [key for key, value in gates.items() if not value]
    return {
        "passed": retained,
        "alpha_checks_passed": alpha_checks_passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed_gates,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": round(max_drawdown_delta, 6),
        "min_survival_rate": round(min_survival_rate, 6),
        "extra_capacity_target_trade_count": extra_capacity_target_trade_count,
        "requires_parity_before_promotion": True,
    }


def _prediction() -> dict[str, Any]:
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
        if isinstance(ticket.get("prediction"), dict):
            return ticket["prediction"]
    return {
        "success_probability": 0.40,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "window_regression",
            "capacity_not_distinct_from_no_core_gate",
            "concentration_failed",
            "baseline_matches_docs",
        ],
        "confidence_reason": "Fallback copied from ticket reservation intent.",
        "recorded_at": "2026-06-01T10:07:36+00:00",
    }


def _calibration(
    prediction: dict[str, Any],
    gate4: dict[str, Any],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    actual_success = 1 if gate4["passed"] else 0
    probability = float(prediction.get("success_probability") or 0.0)
    realized = gate4["failed_gates"]
    predicted_failure_modes = prediction.get("main_failure_modes") or []
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual_success) ** 2, 6),
        "actual_ev_delta": aggregate["comparison"]["expected_value_score_delta"],
        "actual_pnl_delta": aggregate["comparison"]["strategy_total_pnl_delta"],
        "predicted_failure_modes": predicted_failure_modes,
        "realized_failure_mode": realized,
        "predicted_failure_mode_hit": any(
            "window" in mode
            and (
                "all_windows_expected_value_improved" in realized
                or "all_windows_pnl_improved" in realized
            )
            or "capacity" in mode and "distinct_from_no_core_gate" in realized
            or "concentration" in mode and "concentration_guard_passed" in realized
            or "baseline" in mode and "baseline_matches_docs" in realized
            for mode in predicted_failure_modes
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": payload["gate4"]["decision"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Filtered accepted free-data cross-source consensus replay candidates to "
            "signal dates where baseline core positions left unused capacity."
        ),
        "change_type": "default_off_paper_capacity_gate",
        "mechanism_family": "default_off_paper_capacity_gate",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260601-015",
            "exp-20260601-017",
            "exp-20260601-001",
            "exp-20260531-030",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_replacement_value_capacity_discriminator",
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "parameters": payload["rule"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": {
            **comparison,
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "extra_capacity_target_trade_count": payload["gate4"][
                "extra_capacity_target_trade_count"
            ],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["capacity_target_trade_count"],
                "extra_capacity_target_trade_count": row["extra_capacity_target_trade_count"],
            }
            for row in payload["results"]
        ],
        "production_impact": PRODUCTION_IMPACT,
        "decision_basis": payload["gate4"],
        "rejection_reason": "; ".join(payload["gate4"]["failed_gates"]) or None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} accepted consensus core-capacity-available",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: `{comp['expected_value_score_delta']:+.4f}`",
        f"- Aggregate PnL delta: `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- Target trades: `{payload['target_summary']['target_trade_count']}`",
        f"- Extra target trades beyond no-core gate: `{payload['gate4']['extra_capacity_target_trade_count']}`",
        f"- Max positive ticker share: `{payload['target_summary']['max_single_positive_share']}`",
        f"- Positive PnL HHI: `{payload['target_summary']['positive_pnl_hhi']}`",
        f"- Baseline matches docs: `{payload['baseline_drift']['matches_all_windows']}`",
        "",
        "## Three-Window Evidence",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | capacity trades | no-core trades | extra trades | pass candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row['label']} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['comparison']['expected_value_score_delta']:+.4f} | "
            f"${row['comparison']['strategy_total_pnl_delta']:+,.2f} | "
            f"{row['capacity_target_trade_count']} | {row['no_core_target_trade_count']} | "
            f"{row['extra_capacity_target_trade_count']} | {row['capacity_pass_candidate_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
            "No production orders, core ranking/sizing/exits, LLM/news inputs, "
            "watchlists, or shared adapters changed in this replay.",
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "observed_only" if not payload["gate4"]["passed"] else "accepted",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
        for item in experiments:
            if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
                item["status"] = ticket["status"]
                item["decision"] = payload["gate4"]["decision"]
                item["completed_at"] = payload["completed_at"]
                item["artifact"] = _repo_rel(OUT_JSON)
                item["log"] = _repo_rel(LOG_JSON)
                item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ]
                item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ]
                break
    _write_json(REGISTRY_JSON, registry)


def run() -> dict[str, Any]:
    gate2 = source.base._audit_open_positions()
    if not gate2.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2}")

    results, core_metrics_by_window, target_trades_by_window = _run_windows()
    aggregate = _aggregate(results)
    target_summary = _target_summary(target_trades_by_window)
    baseline_drift = _baseline_drift(core_metrics_by_window)
    gate4 = _judge(aggregate, results, target_summary, baseline_drift)
    prediction = _prediction()
    calibration = _calibration(prediction, gate4, aggregate)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "preflight": {
            "alpha_hypothesis": (
                "Accepted free-data consensus candidates should have cleaner activation "
                "value when admitted only on dates where the core replay still leaves "
                "unused position capacity after baseline entries."
            ),
            "category": "candidate_pool / capital_allocation_capacity",
            "playbook_alignment": (
                "Follows the playbook's default-off candidate-pool sleeve maturation "
                "queue and focuses on replacement-value/capacity context rather than "
                "LLM soft-ranking, state-surface retunes, source-count/cooldown/hold/"
                "notional retunes, or noise ticker expansion."
            ),
            "history_check": {
                "exp-20260531-030": "accepted free-data consensus replay lead",
                "exp-20260601-001": "shared observe-only free-data consensus adapter",
                "exp-20260601-015": "positive no-core capacity gate, blocked by baseline drift",
                "exp-20260601-017": "rejected liquidity-efficiency gate on the same consensus pool",
            },
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_standard": (
                "docs/backtesting.md three-window before/after comparison. Retain only if "
                "aggregate EV/PnL and all three windows improve, risk/sample/concentration "
                "guards pass, the result is distinct from exp-20260601-015, and baseline/parity is clean."
            ),
            "reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260601_018_accepted_consensus_core_capacity_available.py"
            ),
        },
        "prediction": prediction,
        "calibration": calibration,
        "rule": {
            "rule_version": RULE_VERSION,
            "source_adapter_experiment_id": "exp-20260601-001",
            "source_replay_experiment_id": "exp-20260531-030",
            "capacity_gate": "admit only if active core positions after signal-date close are below MAX_POSITIONS",
            "max_core_positions": MAX_POSITIONS,
            "base_notional_usd": source.BASE_NOTIONAL_USD,
            "hold_days": source.HOLD_DAYS,
            "max_paper_trades_per_day": source.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": source.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate1": {
            "source": "docs/backtesting.md canonical three-window replay",
            "core_baseline_metrics": core_metrics_by_window,
            "baseline_drift": baseline_drift,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2,
            "runtime_fields": [
                "accepted free-data source paper rows",
                "baseline core trade entry_date and exit_date",
                "MAX_POSITIONS from quant/constants.py",
                "entry_date and target_price in operator_inputs/open_positions.json",
            ],
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in results) >= 0.05,
            "note": "No core/live filter was added; this is a default-off paper capacity discriminator.",
            "survival_by_window": {
                row["label"]: row["after"].get("survival_rate") for row in results
            },
        },
        "gate4": gate4,
        "aggregate": aggregate,
        "baseline_drift": baseline_drift,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "next_retry_requires": [
            "do not retry nearby consensus capacity gates on the frozen sample without clean baseline parity or forward rows",
            "clean current-code baseline parity versus docs/backtesting.md before any positive retention",
            "shared production/backtest capacity adapter before retention",
            "forward closed replacement-value rows before activation",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, aggregate["before"])
    _write_json(AFTER_JSON, aggregate["after"])
    _write_json(LOG_JSON, _experiment_log_record(payload))
    _write_card(payload)
    _update_ticket_and_registry(payload)
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_record(payload))
    return payload


def main() -> None:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "gate4": payload["gate4"],
                "target_summary": {
                    key: payload["target_summary"][key]
                    for key in (
                        "target_trade_count",
                        "target_trade_pnl_usd",
                        "pnl_by_window",
                        "max_single_positive_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
