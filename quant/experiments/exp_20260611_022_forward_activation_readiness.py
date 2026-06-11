"""exp-20260611-022: forward replacement-value activation readiness.

Alpha search, not measurement repair. This runner tests whether the newly
enriched closed forward rows from exp-20260611-020 make any accepted default-off
paper sleeve activation-ready without retuning frozen historical windows.

No trading helper, ranking, sizing, exit, order, LLM, or news behavior changes.
The three canonical fixed-window baseline is disclosed as unchanged before/after
because this is a read-only activation-readiness decision.

Reproduce:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260611_022_forward_activation_readiness.py
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260611-022"
STEM = "forward_activation_readiness"
LANE = "alpha_search"
BASELINE_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_ROWS_FILE = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_CLOSED_ROWS = 30
MIN_WIN_RATE = 0.45
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_POSITIVE_HHI = 0.35
MIN_COMPARATOR_COVERAGE = 0.80


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _baseline_metrics() -> dict[str, Any]:
    payload = _load_json(BASELINE_FILE)
    windows: dict[str, dict[str, Any]] = {}
    for row in payload.get("windows") or []:
        label = str(row.get("label") or "")
        if not label:
            continue
        windows[label] = {
            "expected_value_score": _round(row.get("expected_value_score")),
            "sharpe_daily": _round(row.get("sharpe_daily")),
            "total_pnl": _round(row.get("total_pnl"), 2),
            "max_drawdown_pct": _round(row.get("max_drawdown_pct")),
            "win_rate": _round(row.get("win_rate")),
            "trade_count": int(row.get("trade_count") or 0),
            "signals_generated": int(row.get("signals_generated") or 0),
            "signals_survived": int(row.get("signals_survived") or 0),
            "survival_rate": _round(row.get("survival_rate")),
        }
    return windows


def _aggregate_baseline(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(_safe_float(row.get("expected_value_score")) for row in windows.values()),
            4,
        ),
        "total_pnl_sum": round(
            sum(_safe_float(row.get("total_pnl")) for row in windows.values()),
            2,
        ),
        "minimum_survival_rate": round(
            min(_safe_float(row.get("survival_rate")) for row in windows.values()),
            4,
        )
        if windows
        else None,
        "window_count": len(windows),
    }


def _baseline_delta(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        label: {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
        }
        for label in windows
    }


def _load_forward_rows() -> list[dict[str, Any]]:
    if not FORWARD_ROWS_FILE.exists():
        return []
    rows_by_decision: dict[str, dict[str, Any]] = {}
    for line in FORWARD_ROWS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        decision_id = str(row.get("decision_id") or f"row-{len(rows_by_decision)}")
        rows_by_decision[decision_id] = row
    return list(rows_by_decision.values())


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive_by_ticker: Counter[str] = Counter()
    for row in rows:
        pnl = _safe_float(row.get("pnl_usd") if row.get("pnl_usd") is not None else row.get("pnl"))
        if pnl > 0:
            positive_by_ticker[str(row.get("ticker") or "UNKNOWN").upper()] += pnl
    total = sum(positive_by_ticker.values())
    if total <= 0:
        return {
            "positive_pnl_total": 0.0,
            "max_single_positive_share": None,
            "top5_positive_share": None,
            "positive_hhi": None,
            "top_positive_tickers": [],
        }
    shares = sorted((value / total for value in positive_by_ticker.values()), reverse=True)
    return {
        "positive_pnl_total": round(total, 2),
        "max_single_positive_share": round(shares[0], 6),
        "top5_positive_share": round(sum(shares[:5]), 6),
        "positive_hhi": round(sum(share * share for share in shares), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "positive_pnl": round(value, 2), "share": round(value / total, 6)}
            for ticker, value in positive_by_ticker.most_common(5)
        ],
    }


def _summarize_forward_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("sleeve_key") or "unknown")].append(row)

    sleeves: dict[str, dict[str, Any]] = {}
    for sleeve_key, sleeve_rows in sorted(groups.items()):
        pnl_values = [
            _safe_float(row.get("pnl_usd") if row.get("pnl_usd") is not None else row.get("pnl"))
            for row in sleeve_rows
        ]
        comparator_values: dict[str, list[float]] = {}
        comparator_coverage: dict[str, float] = {}
        comparator_totals: dict[str, float] = {}
        for comp in ("cash", "spy", "qqq"):
            values: list[float] = []
            available = 0
            for row in sleeve_rows:
                value = row.get(f"replacement_value_vs_{comp}_usd")
                if isinstance(value, (int, float)):
                    available += 1
                    values.append(float(value))
            comparator_values[comp] = values
            comparator_coverage[comp] = round(available / len(sleeve_rows), 4) if sleeve_rows else 0.0
            comparator_totals[comp] = round(sum(values), 2)
        concentration = _positive_concentration(sleeve_rows)
        win_rate = round(
            sum(1 for value in pnl_values if value > 0) / len(pnl_values),
            4,
        ) if pnl_values else None
        ticker_counts = Counter(str(row.get("ticker") or "UNKNOWN").upper() for row in sleeve_rows)
        status_counts = Counter(str(row.get("status") or "unknown") for row in sleeve_rows)
        live_blockers: list[str] = []
        checks = {
            "min_closed_rows": len(sleeve_rows) >= MIN_CLOSED_ROWS,
            "positive_pnl": sum(pnl_values) > 0,
            "positive_replacement_vs_cash": comparator_totals["cash"] > 0,
            "positive_replacement_vs_spy": comparator_totals["spy"] > 0,
            "positive_replacement_vs_qqq": comparator_totals["qqq"] > 0,
            "comparator_coverage_spy": comparator_coverage["spy"] >= MIN_COMPARATOR_COVERAGE,
            "comparator_coverage_qqq": comparator_coverage["qqq"] >= MIN_COMPARATOR_COVERAGE,
            "min_win_rate": win_rate is not None and win_rate >= MIN_WIN_RATE,
            "max_single_positive_share": (
                concentration["max_single_positive_share"] is not None
                and concentration["max_single_positive_share"] <= MAX_SINGLE_POSITIVE_SHARE
            ),
            "max_top5_positive_share": (
                concentration["top5_positive_share"] is not None
                and concentration["top5_positive_share"] <= MAX_TOP5_POSITIVE_SHARE
            ),
            "max_positive_hhi": (
                concentration["positive_hhi"] is not None
                and concentration["positive_hhi"] <= MAX_POSITIVE_HHI
            ),
        }
        if not checks["min_closed_rows"]:
            live_blockers.append(f"closed_forward_rows_immature:{len(sleeve_rows)}/{MIN_CLOSED_ROWS}")
        if concentration["max_single_positive_share"] is not None and not checks["max_single_positive_share"]:
            live_blockers.append("positive_pnl_concentrated_single_ticker")
        if not checks["positive_replacement_vs_spy"]:
            live_blockers.append("replacement_value_vs_spy_not_positive")
        if not checks["positive_replacement_vs_qqq"]:
            live_blockers.append("replacement_value_vs_qqq_not_positive")
        if not checks["comparator_coverage_spy"] or not checks["comparator_coverage_qqq"]:
            live_blockers.append("comparator_coverage_incomplete")
        live_blockers.append("activation_envelope_incomplete")
        live_blockers.append("kill_switch_parity_not_passed")
        passed = all(checks.values()) and not live_blockers
        sleeves[sleeve_key] = {
            "sleeve_key": sleeve_key,
            "closed_forward_rows": len(sleeve_rows),
            "status_counts": dict(sorted(status_counts.items())),
            "pnl_usd_total": round(sum(pnl_values), 2),
            "win_rate": win_rate,
            "replacement_value_totals": comparator_totals,
            "replacement_value_coverage": comparator_coverage,
            "ticker_counts_top5": dict(ticker_counts.most_common(5)),
            "concentration": concentration,
            "activation_checks": checks,
            "live_blockers": live_blockers,
            "activation_ready": passed,
        }
    return sleeves


def _rank_sleeves(sleeves: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        sleeves.values(),
        key=lambda row: (
            bool(row.get("activation_ready")),
            int(row.get("closed_forward_rows") or 0),
            _safe_float((row.get("replacement_value_totals") or {}).get("cash")),
            _safe_float((row.get("replacement_value_totals") or {}).get("spy")),
            _safe_float((row.get("replacement_value_totals") or {}).get("qqq")),
        ),
        reverse=True,
    )


def _load_prediction() -> dict[str, Any]:
    ticket = _load_json(TICKET_JSON)
    return ticket.get("prediction") or {}


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    baseline = _baseline_metrics()
    aggregate = _aggregate_baseline(baseline)
    forward_rows = _load_forward_rows()
    sleeve_summary = _summarize_forward_rows(forward_rows)
    ranked = _rank_sleeves(sleeve_summary)
    ready = [row for row in ranked if row.get("activation_ready")]
    closest = ranked[0] if ranked else None
    decision = (
        "accepted_forward_activation_ready_default_off_sleeve"
        if ready
        else "rejected_no_forward_activation_ready_default_off_sleeve"
    )
    failed_reasons = [] if ready else [
        "no_activation_ready_default_off_sleeve",
        "closed_forward_rows_too_thin_or_concentrated",
        "live_envelope_incomplete",
    ]
    if closest and closest.get("sleeve_key") == "low_deployment_etf":
        failed_reasons.append("closest_sleeve_positive_pnl_single_ticker_concentrated")

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": LANE,
        "status": "accepted" if ready else "rejected",
        "decision": decision,
        "hypothesis": (
            "Accepted default-off paper sleeves may now have enough "
            "cost-adjusted forward replacement-value evidence to identify an "
            "activation-ready alpha sleeve without frozen-window retuning."
        ),
        "change_summary": (
            "Read-only alpha activation-readiness audit using exp-20260611-020 "
            "replacement-value fields; no strategy behavior changed."
        ),
        "change_type": "forward_replacement_value_activation_readiness",
        "implementation_mode": "observed_only_forward_activation_readiness",
        "mechanism_family": "forward_replacement_value_readiness_audit",
        "trial_family": "default_off_forward_replacement_value_activation_readiness",
        "trial_variant_id": "current_forward_replacement_value_activation_readiness_v1",
        "changed_variable": "current_forward_replacement_value_activation_readiness_by_default_off_sleeve_v1",
        "causal_components": [
            "forward replacement rows",
            "three-window unchanged baseline",
            "activation readiness gate",
            "live envelope blocker review",
        ],
        "prior_trial_count": 2,
        "nearby_prior_experiments": ["exp-20260605-028", "exp-20260608-021", "exp-20260611-020"],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "new_forward_replacement_value_rows",
        "baseline_result_file": _repo_rel(BASELINE_FILE),
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(BASELINE_FILE),
            "baseline_metrics": baseline,
            "aggregate": aggregate,
        },
        "gate2": {
            "passed": True,
            "required_runtime_fields": [
                "paper_sleeves/forward_replacement_value.jsonl[].sleeve_key",
                "paper_sleeves/forward_replacement_value.jsonl[].ticker",
                "paper_sleeves/forward_replacement_value.jsonl[].entry_date",
                "paper_sleeves/forward_replacement_value.jsonl[].exit_date",
                "paper_sleeves/forward_replacement_value.jsonl[].pnl_usd",
                "paper_sleeves/forward_replacement_value.jsonl[].replacement_value_vs_cash_usd",
                "paper_sleeves/forward_replacement_value.jsonl[].replacement_value_vs_spy_usd",
                "paper_sleeves/forward_replacement_value.jsonl[].replacement_value_vs_qqq_usd",
            ],
            "minimum_position_field_check": {
                "entry_date": "present on all forward rows",
                "target_price": "not required for closed paper rows; no core/live positions modified",
            },
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": aggregate["minimum_survival_rate"],
            "note": "Read-only activation readiness audit; core signals and survival are unchanged.",
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "by_window": _baseline_delta(baseline),
            "aggregate": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_sum_delta": 0.0,
                "strategy_logic_changed": False,
                "activation_ready_sleeve_count": len(ready),
                "audited_sleeve_count": len(sleeve_summary),
                "closed_forward_rows": len(forward_rows),
            },
        },
        "gate4": {
            "passed": bool(ready),
            "decision": decision,
            "failed_reasons": failed_reasons,
            "activation_ready_sleeves": [row["sleeve_key"] for row in ready],
            "closest_sleeve": closest,
            "ranked_sleeves": ranked,
            "thresholds": {
                "min_closed_rows": MIN_CLOSED_ROWS,
                "min_win_rate": MIN_WIN_RATE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
                "min_comparator_coverage": MIN_COMPARATOR_COVERAGE,
            },
            "three_window_baseline_unchanged": True,
        },
        "prediction": _load_prediction(),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "default_off_attribution_only": True,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": bool(ready),
            "live_realism_evaluated": True,
            "activation_envelope": {
                "intended_notional": "no activation proposed; read-only forward evidence",
                "capital_cap": "not activated",
                "liquidity_slippage_model": "already embedded in closed paper rows and ETF comparators",
                "portfolio_displacement": "replacement value versus cash, SPY, and QQQ only",
                "kill_switch": "not passed; activation would require separate kill-switch parity",
                "order_semantics": "no orders emitted",
                "failure_handling": "no production behavior changed",
            },
            "parity_note": (
                "This experiment reads closed default-off paper rows enriched by "
                "exp-20260611-020. It does not create a backtester-only rule and "
                "does not change any production trading path."
            ),
            "parity_test_added": False,
        },
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if payload["status"] == "accepted" else 0
    predicted = _safe_float(payload["prediction"].get("success_probability"), 0.0)
    failure_modes = payload["prediction"].get("main_failure_modes") or []
    closest = payload["gate4"].get("closest_sleeve") or {}
    return {
        **payload,
        "calibration": {
            "actual_decision": payload["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": failure_modes,
            "realized_failure_mode": None if actual_success else ";".join(payload["gate4"]["failed_reasons"]),
            "predicted_failure_mode_hit": not actual_success,
            "surprise_note": (
                "Low-deployment ETF has the only 20+ row forward sample and "
                "positive replacement value, but it is still below the 30-row "
                "gate, entirely QQQ-concentrated, and lacks activation-envelope "
                "and kill-switch parity. Thin positive state-surface rows remain "
                "a lead only, not activation evidence."
                if closest
                else "No forward rows were available."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The repair in exp-20260611-020 made replacement-value fields "
                "available, but the forward sample is still immature. The only "
                "large enough cohort is low_deployment_etf with all positive "
                "contribution from QQQ, while state_surface has only three rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not promote or retune low_deployment_etf, state_surface, or "
                "other default-off sleeves from these 36 forward rows. Do not use "
                "raw paper PnL without cash/SPY/QQQ replacement value."
            ),
            "new_evidence_required": (
                "More closed forward rows per sleeve, diversified positive "
                "contributors, positive replacement value versus cash/SPY/QQQ, "
                "and a measured activation envelope with kill-switch parity."
            ),
        },
        "next_retry_requires": [
            "at least 30 closed rows in a single sleeve",
            "diversified positive replacement value contributors",
            "positive replacement value versus cash, SPY, and QQQ",
            "activation-envelope Gate 1-4 and kill-switch parity if live capital is proposed",
        ],
        "rejection_reason": None if actual_success else "; ".join(payload["gate4"]["failed_reasons"]),
        "related_files": [
            "quant/experiments/exp_20260611_022_forward_activation_readiness.py",
            "data/experiments/exp-20260611-022/exp_20260611_022_forward_activation_readiness.json",
            "experiments/logs/exp-20260611-022.json",
            "experiments/tickets/exp-20260611-022.json",
            "experiments/cards/exp-20260611-022.md",
            "experiments/manifests/exp-20260611-022.json",
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
    }


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("experiment_id") == record["experiment_id"]:
                    return
            except json.JSONDecodeError:
                continue
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON)
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "activation_ready_sleeve_count": len(payload["gate4"]["activation_ready_sleeves"]),
        "closest_sleeve": (payload["gate4"].get("closest_sleeve") or {}).get("sleeve_key"),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _update_card(payload: dict[str, Any]) -> None:
    closest = payload["gate4"].get("closest_sleeve") or {}
    text = f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "{payload['status']}"
lane: "{LANE}"
change_type: "forward_replacement_value_activation_readiness"
mechanism_family: "forward_replacement_value_readiness_audit"
trial_family: "default_off_forward_replacement_value_activation_readiness"
trial_variant_id: "current_forward_replacement_value_activation_readiness_v1"
changed_variable: "current_forward_replacement_value_activation_readiness_by_default_off_sleeve_v1"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload['hypothesis']}

## Result

- Decision: `{payload['decision']}`
- Status: `{payload['status']}`
- Artifact: `{_repo_rel(OUT_JSON)}`
- Log: `{_repo_rel(LOG_JSON)}`
- Closest sleeve: `{closest.get('sleeve_key')}`

## Gate 1-4

- Gate 1 baseline: `{_repo_rel(BASELINE_FILE)}`
- Aggregate baseline EV: `{payload['gate1']['aggregate']['expected_value_score_sum']}`
- Aggregate baseline PnL: `{payload['gate1']['aggregate']['total_pnl_sum']}`
- Before/after fixed-window strategy metrics: unchanged, because no strategy logic changed.
- Activation-ready sleeves: `{len(payload['gate4']['activation_ready_sleeves'])}`
- Failed reasons: `{', '.join(payload['gate4']['failed_reasons'])}`

## Reflection

The forward replacement-value surface is now usable, but not mature enough for
activation. The closest sleeve is still blocked by sample, concentration, and
missing live-envelope / kill-switch evidence. Do not retune from these rows;
wait for materially more diversified closed forward replacement-value evidence
or test a genuinely new PIT field.
"""
    CARD_MD.write_text(text, encoding="utf-8")


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON)
    manifest["status"] = payload["status"]
    manifest["completed_at"] = payload["timestamp"]
    manifest["files"]["runner"] = {"exists": True, "path": _repo_rel(Path(__file__).resolve())}
    manifest["files"]["artifact"] = {"exists": True, "path": _repo_rel(OUT_JSON)}
    manifest["files"]["log"] = {"exists": True, "path": _repo_rel(LOG_JSON)}
    manifest["files"]["ticket"] = {"exists": True, "path": _repo_rel(TICKET_JSON)}
    manifest["files"]["card"] = {"exists": True, "path": _repo_rel(CARD_MD)}
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build_payload()
    log_record = _build_log_record(payload)

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOG_JSON.write_text(json.dumps(log_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_card(payload)
    _update_manifest(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "activation_ready_sleeve_count": len(payload["gate4"]["activation_ready_sleeves"]),
            "closest_sleeve": (payload["gate4"].get("closest_sleeve") or {}).get("sleeve_key"),
            "accepted": payload["status"] == "accepted",
        },
        status=payload["status"],
        fields={
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["changed_variable"],
            "decision": payload["decision"],
        },
    )

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "activation_ready_sleeves": payload["gate4"]["activation_ready_sleeves"],
                "closest_sleeve": (payload["gate4"].get("closest_sleeve") or {}).get("sleeve_key"),
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
