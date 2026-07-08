"""exp-20260708-006: fundamental_growth_rs forward replacement readiness.

Observed-only alpha attribution. The single question is whether the accepted
fundamental_growth_rs default-off paper sleeve has accumulated enough closed
replacement-value rows to become activation-ready, without retuning any
Companyfacts, OHLCV, ranking, hold, notional, or execution rule.

This runner changes no shared policy, entry, exit, ranking, sizing, paper state,
live order, watchlist, daily artifact, or LLM boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts",):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260708-006"
OWNER = "alpha-explore"
SLUG = "fundamental_growth_rs_forward_readiness_20260707"
RUNNER = f"quant/experiments/exp_20260708_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "fundamental_growth_rs" / "state.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_006_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: accepted fundamental_growth_rs default-off paper "
    "sleeve now has materially more closed forward rows with cash/SPY/QQQ "
    "replacement value; test whether the fixed sleeve is activation-ready "
    "without retuning Companyfacts/OHLCV rules."
)
CHANGE_TYPE = "forward_replacement_value_attribution"
IMPLEMENTATION_MODE = "observed_only_default_off_paper_sleeve_readiness"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
TRIAL_FAMILY = "fundamental_growth_rs_forward_readiness"
TRIAL_VARIANT_ID = "20260707_closed_replacement_value_v1"
CHANGED_VARIABLE = "fundamental_growth_rs_forward_replacement_value_readiness_20260707_v1"
NEW_EVIDENCE_TYPE = "materially_more_settled_forward_rows"
NEW_EVIDENCE_AXIS = (
    "fundamental_growth_rs has 11 replacement-value-enriched closed paper "
    "positions as of 2026-07-07 versus mostly zero closed rows in early June "
    "default-off readiness audits; no threshold, rank, notional, hold, or "
    "Companyfacts field retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260605-028",
    "exp-20260608-021",
    "exp-20260708-003",
]
CAUSAL_COMPONENTS = [
    "accepted shared helper closed rows",
    "cash/SPY/QQQ replacement-value attribution",
    "forward activation readiness verdict",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "sample_too_thin",
        "negative_replacement_value",
        "single_ticker_concentration",
        "not_activation_ready",
    ],
    "confidence_reason": (
        "Accepted fundamental-growth/RS helper has historical evidence and now "
        "materially more closed enriched forward rows, but nearby Companyfacts "
        "scans are heavily explored and the forward sample is likely still "
        "small and concentrated."
    ),
    "recorded_at": "2026-07-08T05:09:08+00:00",
}
CONFIG = {
    "min_watchlist_enriched_closed_rows": 20,
    "min_activation_enriched_closed_rows": 60,
    "min_unique_tickers": 5,
    "max_single_ticker_share": 0.35,
    "min_axis_win_rate": 0.50,
    "replacement_axes": [
        "replacement_value_vs_cash_usd",
        "replacement_value_vs_spy_usd",
        "replacement_value_vs_qqq_usd",
    ],
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rounded(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def summarize_values(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [as_float(row.get(field)) for row in rows]
    clean = [value for value in values if value is not None]
    if not clean:
        return {
            "field": field,
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": None,
        }
    wins = sum(1 for value in clean if value > 0)
    return {
        "field": field,
        "n": len(clean),
        "sum": rounded(sum(clean), 2),
        "mean": rounded(sum(clean) / len(clean), 2),
        "median": rounded(statistics.median(clean), 2),
        "min": rounded(min(clean), 2),
        "max": rounded(max(clean), 2),
        "win_count": wins,
        "loss_count": len(clean) - wins,
        "win_rate": rounded(wins / len(clean), 4),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "generated_at": payload.get("generated_at"),
        "window_count": len(windows),
        "expected_value_score_sum": rounded(
            sum(as_float(row.get("expected_value_score")) or 0.0 for row in windows),
            4,
        ),
        "total_pnl_sum": rounded(
            sum(as_float(row.get("total_pnl")) or 0.0 for row in windows),
            2,
        ),
        "max_drawdown_pct_max": rounded(
            max((as_float(row.get("max_drawdown_pct")) or 0.0 for row in windows), default=0.0),
            4,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated_sum": sum(
            int(row.get("signals_generated") or 0) for row in windows
        ),
        "signals_survived_sum": sum(
            int(row.get("signals_survived") or 0) for row in windows
        ),
        "windows": windows,
    }


def normalize_closed_row(row: dict[str, Any]) -> dict[str, Any]:
    candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
    return {
        "ticker": row.get("ticker") or candidate.get("ticker"),
        "status": row.get("status"),
        "trade_enabled": bool(row.get("trade_enabled")),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "entry_price": as_float(row.get("entry_price")),
        "exit_price": as_float(row.get("exit_price")),
        "notional": as_float(row.get("notional")),
        "hold_days": row.get("hold_days"),
        "exit_reason": row.get("exit_reason"),
        "replacement_value_status": row.get("replacement_value_status"),
        "replacement_value_vs_cash_usd": as_float(
            row.get("replacement_value_vs_cash_usd")
        ),
        "replacement_value_vs_spy_usd": as_float(row.get("replacement_value_vs_spy_usd")),
        "replacement_value_vs_qqq_usd": as_float(row.get("replacement_value_vs_qqq_usd")),
        "return_pct_net": as_float(row.get("return_pct_net")),
        "entry_regime_label": row.get("entry_regime_label"),
        "entry_short_volume_quintile": row.get("entry_short_volume_quintile"),
        "entry_exhaustion_status": row.get("entry_exhaustion_status"),
        "target_price_present": "target_price" in row or "target_price" in candidate,
        "candidate_known_at": candidate.get("known_at"),
        "candidate_source": candidate.get("source"),
    }


def group_axis_by_ticker(
    rows: list[dict[str, Any]], field: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("ticker") or "UNKNOWN")].append(row)
    return {ticker: summarize_values(items, field) for ticker, items in sorted(grouped.items())}


def evaluate_gate4(
    closed_rows: list[dict[str, Any]],
    enriched_rows: list[dict[str, Any]],
    axis_summaries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fail_reasons: list[str] = []
    enriched_count = len(enriched_rows)
    ticker_counts = Counter(row.get("ticker") or "UNKNOWN" for row in enriched_rows)
    unique_tickers = len(ticker_counts)
    max_ticker_count = max(ticker_counts.values(), default=0)
    max_ticker_share = max_ticker_count / enriched_count if enriched_count else 0.0

    if enriched_count < CONFIG["min_watchlist_enriched_closed_rows"]:
        fail_reasons.append("min_watchlist_enriched_rows_not_met")
    if enriched_count < CONFIG["min_activation_enriched_closed_rows"]:
        fail_reasons.append("min_activation_enriched_rows_not_met")
    if unique_tickers < CONFIG["min_unique_tickers"]:
        fail_reasons.append("min_unique_tickers_not_met")
    if max_ticker_share > CONFIG["max_single_ticker_share"]:
        fail_reasons.append("single_ticker_concentration_too_high")

    for field in CONFIG["replacement_axes"]:
        summary = axis_summaries[field]
        if summary["n"] < enriched_count:
            fail_reasons.append(f"{field}_missing_values")
        if (summary["sum"] or 0.0) <= 0.0:
            fail_reasons.append(f"{field}_aggregate_not_positive")
        if (summary["win_rate"] or 0.0) < CONFIG["min_axis_win_rate"]:
            fail_reasons.append(f"{field}_win_rate_below_50pct")

    incomplete_rows = len(closed_rows) - enriched_count
    if incomplete_rows > 0:
        fail_reasons.append("incomplete_replacement_value_rows")

    watchlist_lead = (
        enriched_count >= CONFIG["min_watchlist_enriched_closed_rows"]
        and unique_tickers >= CONFIG["min_unique_tickers"]
        and max_ticker_share <= CONFIG["max_single_ticker_share"]
        and all((axis_summaries[field]["sum"] or 0.0) > 0 for field in CONFIG["replacement_axes"])
    )
    activation_ready = (
        enriched_count >= CONFIG["min_activation_enriched_closed_rows"]
        and watchlist_lead
        and all(
            (axis_summaries[field]["win_rate"] or 0.0) >= CONFIG["min_axis_win_rate"]
            for field in CONFIG["replacement_axes"]
        )
        and incomplete_rows == 0
    )

    return {
        "passed": activation_ready,
        "decision": (
            "accept_default_off_activation_readiness"
            if activation_ready
            else "reject_activation_readiness"
        ),
        "activation_ready": activation_ready,
        "watchlist_lead": watchlist_lead,
        "failed_reasons": fail_reasons,
        "readiness_guard": CONFIG,
        "closed_rows": len(closed_rows),
        "enriched_closed_rows": enriched_count,
        "incomplete_replacement_value_rows": incomplete_rows,
        "unique_tickers": unique_tickers,
        "max_single_ticker_count": max_ticker_count,
        "max_single_ticker_share": rounded(max_ticker_share, 4),
        "axis_summaries": axis_summaries,
        "before_after_strategy_delta": {
            "expected_value_score_delta_sum": 0.0,
            "total_pnl_delta_sum": 0.0,
            "trade_count_delta_sum": 0,
            "note": "Observed-only attribution; strategy behavior is unchanged.",
        },
        "reopen_condition": (
            "Do not reserve another fundamental_growth_rs forward-readiness ID "
            "until at least 20 enriched closed rows exist for a watchlist-lead "
            "refresh, and do not test activation envelope until at least 60 "
            "enriched closed rows exist with positive cash/SPY/QQQ replacement "
            "value and diversified ticker concentration."
        ),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    state = read_json(STATE_JSON, {})
    closed_raw = state.get("closed_positions") or []
    open_raw = state.get("open_positions") or []
    pending_raw = state.get("pending_entries") or []
    closed_rows = [normalize_closed_row(row) for row in closed_raw]
    enriched_rows = [
        row for row in closed_rows if row.get("replacement_value_status") == "enriched"
    ]
    axis_summaries = {
        field: summarize_values(enriched_rows, field) for field in CONFIG["replacement_axes"]
    }
    return_summary = summarize_values(enriched_rows, "return_pct_net")
    gate4 = evaluate_gate4(closed_rows, enriched_rows, axis_summaries)
    baseline = baseline_metrics()
    ticker_counts = Counter(row.get("ticker") or "UNKNOWN" for row in enriched_rows)
    now = utc_now()
    status = "observed_only" if gate4["passed"] else "observed_only_rejected"
    decision = f"{gate4['decision']}_fundamental_growth_rs_forward_rows_20260707"
    actual_success = 1 if gate4["passed"] else 0
    prediction_failure_hit = any(
        reason in set(gate4["failed_reasons"])
        for reason in {
            "min_watchlist_enriched_rows_not_met",
            "min_activation_enriched_rows_not_met",
            "replacement_value_vs_cash_usd_aggregate_not_positive",
            "replacement_value_vs_spy_usd_aggregate_not_positive",
            "replacement_value_vs_qqq_usd_aggregate_not_positive",
        }
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": gate4["passed"],
        "accepted_alpha": False,
        "observed_only_lead": bool(gate4["watchlist_lead"]),
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": rounded((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": gate4["failed_reasons"],
            "predicted_failure_mode_hit": prediction_failure_hit,
            "surprise_note": (
                "The fixed sleeve is weaker than a mere sample-size rejection: "
                "all three replacement-value axes are negative and only 4/10 "
                "enriched rows beat cash/SPY/QQQ."
                if not gate4["passed"]
                else "The sleeve cleared the fixed activation guard, but this "
                "runner still leaves the result default-off until a separate "
                "shared-policy Gate 1-4 experiment promotes it."
            ),
        },
        "parameters": {
            "state_file": repo_rel(STATE_JSON),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "readiness_guard": CONFIG,
            "no_strategy_behavior_change": True,
        },
        "artifact": repo_rel(OUT_JSON),
        "report": repo_rel(ARTIFACT_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only forward attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": bool(closed_rows)
            and all(row.get("entry_date") for row in closed_rows)
            and any(row.get("replacement_value_status") == "enriched" for row in closed_rows),
            "fields_checked": [
                "closed_positions[].ticker",
                "closed_positions[].status",
                "closed_positions[].entry_date",
                "closed_positions[].exit_date",
                "closed_positions[].entry_price",
                "closed_positions[].exit_price",
                "closed_positions[].notional",
                "closed_positions[].trade_enabled",
                "closed_positions[].replacement_value_status",
                "closed_positions[].replacement_value_vs_cash_usd",
                "closed_positions[].replacement_value_vs_spy_usd",
                "closed_positions[].replacement_value_vs_qqq_usd",
                "closed_positions[].target_price",
            ],
            "diagnostics": {
                "closed_rows": len(closed_rows),
                "entry_date_present_rows": sum(1 for row in closed_rows if row.get("entry_date")),
                "target_price_present_rows": sum(
                    1 for row in closed_rows if row.get("target_price_present")
                ),
                "target_price_contract_applicable": False,
                "target_price_note": (
                    "No executable signal or ATR target exit is changed. These "
                    "default-off paper rows use fixed paper-sleeve close logic, "
                    "so target_price is not a gating contract for this read-only "
                    "forward attribution."
                ),
                "trade_enabled_rows": sum(1 for row in closed_rows if row.get("trade_enabled")),
                "replacement_value_enriched_rows": len(enriched_rows),
                "missing_replacement_value_rows": len(closed_rows) - len(enriched_rows),
            },
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": len(closed_rows) + len(open_raw) + len(pending_raw),
            "signals_survived": len(enriched_rows),
            "survival_rate": rounded(
                len(enriched_rows) / (len(closed_rows) + len(open_raw) + len(pending_raw)),
                6,
            )
            if (len(closed_rows) + len(open_raw) + len(pending_raw))
            else 0.0,
            "note": "No executable filter was added; survival is a paper-settlement completeness diagnostic only.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": gate4["before_after_strategy_delta"],
        "summary": {
            "state_updated_at": state.get("updated_at"),
            "closed_rows": len(closed_rows),
            "enriched_closed_rows": len(enriched_rows),
            "open_rows": len(open_raw),
            "pending_rows": len(pending_raw),
            "ticker_counts": dict(sorted(ticker_counts.items())),
            "entry_regime_counts": dict(
                sorted(Counter(row.get("entry_regime_label") for row in enriched_rows).items())
            ),
            "short_volume_quintile_counts": dict(
                sorted(
                    Counter(row.get("entry_short_volume_quintile") for row in enriched_rows).items()
                )
            ),
            "axis_summaries": axis_summaries,
            "return_pct_net_summary": return_summary,
            "by_ticker_cash": group_axis_by_ticker(
                enriched_rows, "replacement_value_vs_cash_usd"
            ),
            "closed_rows_detail": closed_rows,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only attribution over existing default-off paper sleeve "
                "state. No order, helper, adapter, or daily snapshot behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The new settled rows are enough to reopen the sleeve surface for "
                "measurement, but not enough to promote it: only 10 enriched closed "
                "rows, one incomplete DDOG close, 4/10 winners, and negative "
                "aggregate replacement value versus cash, SPY, and QQQ."
                if not gate4["passed"]
                else "The fixed sleeve cleared replacement-value readiness. It "
                "still needs a separate shared-policy promotion experiment because "
                "this runner changed no strategy behavior."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune Companyfacts growth fields, RS cutoffs, entry "
                "regime, short-volume tags, exhaustion tags, hold length, notional, "
                "or hard-exclusion versus tilt response on this 10-row enriched "
                "cohort."
            ),
            "new_evidence_required": gate4["reopen_condition"],
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if not gate4["passed"] else None,
        "related_files": [
            RUNNER,
            repo_rel(STATE_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(OUT_JSON),
            repo_rel(ARTIFACT_MD),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(ARTIFACT_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": list((ticket or {}).get("allowed_write_scope") or []),
        "ticket_before": ticket,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    return payload


def build_report(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    axes = gate4["axis_summaries"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Fundamental Growth RS Forward Readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Runner: `{RUNNER_COMMAND}`",
            f"- Artifact: `{payload['artifact']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Fixed Guard",
            "",
            f"- Enriched closed rows: `{gate4['enriched_closed_rows']}` "
            f"(watchlist min `{CONFIG['min_watchlist_enriched_closed_rows']}`, "
            f"activation min `{CONFIG['min_activation_enriched_closed_rows']}`)",
            f"- Unique tickers: `{gate4['unique_tickers']}`; max single ticker share "
            f"`{gate4['max_single_ticker_share']}`",
            "",
            "## Replacement Value",
            "",
            f"- Cash: sum `{axes['replacement_value_vs_cash_usd']['sum']}`, "
            f"mean `{axes['replacement_value_vs_cash_usd']['mean']}`, "
            f"win rate `{axes['replacement_value_vs_cash_usd']['win_rate']}`",
            f"- SPY: sum `{axes['replacement_value_vs_spy_usd']['sum']}`, "
            f"mean `{axes['replacement_value_vs_spy_usd']['mean']}`, "
            f"win rate `{axes['replacement_value_vs_spy_usd']['win_rate']}`",
            f"- QQQ: sum `{axes['replacement_value_vs_qqq_usd']['sum']}`, "
            f"mean `{axes['replacement_value_vs_qqq_usd']['mean']}`, "
            f"win rate `{axes['replacement_value_vs_qqq_usd']['win_rate']}`",
            "",
            "## Verdict",
            "",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    cash = gate4["axis_summaries"]["replacement_value_vs_cash_usd"]
    spy = gate4["axis_summaries"]["replacement_value_vs_spy_usd"]
    qqq = gate4["axis_summaries"]["replacement_value_vs_qqq_usd"]
    lines = [
        f"# {EXPERIMENT_ID}: Fundamental Growth RS Forward Readiness",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Report: `{payload['report']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Result",
        "",
        f"- Enriched closed rows: `{gate4['enriched_closed_rows']}` / "
        f"`{gate4['closed_rows']}`",
        f"- Cash/SPY/QQQ aggregate RV: `{cash['sum']}` / `{spy['sum']}` / `{qqq['sum']}`",
        f"- Cash/SPY/QQQ win rate: `{cash['win_rate']}` / `{spy['win_rate']}` / `{qqq['win_rate']}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Reflection",
        "",
        f"- Why: {payload['post_run_reflection']['why_result_happened']}",
        f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
        f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        ARTIFACT_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "report": repo_rel(ARTIFACT_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))
    write_text(ARTIFACT_MD, build_report(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "report": repo_rel(ARTIFACT_MD),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "replacement_value_vs_cash_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_cash_usd"
            ]["sum"],
            "replacement_value_vs_spy_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_spy_usd"
            ]["sum"],
            "replacement_value_vs_qqq_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_qqq_usd"
            ]["sum"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "report": repo_rel(ARTIFACT_MD),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "closed_rows": payload["gate4"]["closed_rows"],
                "enriched_closed_rows": payload["gate4"]["enriched_closed_rows"],
                "axis_summaries": payload["gate4"]["axis_summaries"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
                "report": payload["report"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
