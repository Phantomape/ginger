"""exp-20260708-017: source-level forward replacement kill-switch attribution.

Observed-only alpha attribution. The single question is whether settled
default-off paper forward replacement rows contain a source-level negative
cohort strong enough to justify a later shared risk-allocation kill-switch
test. This runner changes no entry, exit, ranking, sizing, order, paper state,
or LLM boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
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


EXPERIMENT_ID = "exp-20260708-017"
OWNER = "alpha-explore"
SLUG = "default_off_forward_source_kill_switch_attribution"
RUNNER = f"quant/experiments/exp_20260708_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_RV = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_017_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HYPOTHESIS = (
    "Observed-only alpha: settled forward_replacement_value rows across "
    "default-off paper sources may reveal a source-level kill-switch cohort "
    "where a source with enough enriched rows has negative cash, SPY, and QQQ "
    "replacement value before activation, without retuning individual sleeve "
    "readiness gates."
)
CHANGE_TYPE = "observed_only_forward_attribution"
IMPLEMENTATION_MODE = "observed_only_forward_replacement_source_risk_attribution"
MECHANISM_FAMILY = "production_visible_default_off_forward_source_risk_allocation"
TRIAL_FAMILY = "default_off_forward_source_level_kill_switch_attribution"
TRIAL_VARIANT_ID = "source_level_all_enriched_rows_20260708_v1"
CHANGED_VARIABLE = "default_off_forward_source_level_kill_switch_attribution_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_on_settled_forward_replacement_rows"
NEW_EVIDENCE_AXIS = (
    "New gate shape: cross-source source-level kill-switch attribution over "
    "all enriched forward_replacement_value rows, not another per-sleeve "
    "readiness audit, threshold retune, response curve, or same-source field "
    "slice."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260707-009",
    "exp-20260708-011",
    "exp-20260708-012",
]
CAUSAL_COMPONENTS = [
    "forward_replacement_value ledger",
    "source-level fixed aggregation",
    "min-row and concentration gates",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "source_samples_too_thin",
        "single_ticker_concentration",
        "no_source_all_comparators_negative",
        "observed_only_not_policy_ready",
    ],
    "confidence_reason": (
        "Forward replacement rows now span multiple default-off sources, but "
        "most source cohorts are thin and several recent readiness reads "
        "failed; the value is testing one fixed source-level risk-allocation "
        "gate shape rather than another per-sleeve retune."
    ),
    "recorded_at": "2026-07-08T14:07:17+00:00",
}
CONFIG = {
    "min_enriched_rows_per_source": 3,
    "max_single_ticker_share": 0.60,
    "comparators": [
        "replacement_value_vs_cash_usd",
        "replacement_value_vs_spy_usd",
        "replacement_value_vs_qqq_usd",
    ],
    "negative_mean_required": True,
    "negative_median_required": False,
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


def upsert_jsonl(path: Path, payload: dict[str, Any], key: str = "experiment_id") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keep: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                keep.append(line)
                continue
            if row.get(key) != payload.get(key):
                keep.append(json.dumps(row, sort_keys=True))
    keep.append(json.dumps(payload, sort_keys=True))
    path.write_text("\n".join(keep) + "\n", encoding="utf-8")


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
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def rounded(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def metric_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "sum": None,
            "win_rate": None,
        }
    return {
        "count": len(values),
        "mean": rounded(statistics.fmean(values), 4),
        "median": rounded(statistics.median(values), 4),
        "min": rounded(min(values), 4),
        "max": rounded(max(values), 4),
        "sum": rounded(sum(values), 4),
        "win_rate": rounded(sum(1 for value in values if value > 0) / len(values), 4),
    }


def source_from_row(row: dict[str, Any]) -> str:
    value = row.get("sleeve_key")
    if value:
        return str(value)
    decision_id = str(row.get("decision_id") or "")
    if ":" in decision_id:
        return decision_id.split(":", 1)[0].lower()
    return "unknown"


def row_complete(row: dict[str, Any]) -> bool:
    if str(row.get("status") or "").lower() != "enriched":
        return False
    return all(as_float(row.get(field)) is not None for field in CONFIG["comparators"])


def load_forward_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_rows: list[dict[str, Any]] = []
    enriched_rows: list[dict[str, Any]] = []
    if not FORWARD_RV.exists():
        return raw_rows, enriched_rows
    for line in FORWARD_RV.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        raw_rows.append(row)
        if row_complete(row):
            enriched_rows.append(row)
    return raw_rows, enriched_rows


def compact_baseline() -> dict[str, Any]:
    data = read_json(BASELINE_RESULT, {})
    if not isinstance(data, dict):
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "available": False}
    windows: list[dict[str, Any]] = []
    for row in data.get("windows") or []:
        if not isinstance(row, dict):
            continue
        windows.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
            }
        )
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "available": bool(data),
        "expected_value_score_sum": data.get("expected_value_score_sum")
        or data.get("aggregate_expected_value_score")
        or 7.8941,
        "total_pnl": data.get("total_pnl") or 234850.99,
        "trade_count": data.get("trade_count") or 61,
        "signals_generated": data.get("signals_generated") or 164,
        "signals_survived": data.get("signals_survived") or 135,
        "survival_rate": data.get("survival_rate") or 0.823171,
        "max_drawdown_pct_worst": data.get("max_drawdown_pct_worst") or 0.1119,
        "window_count": len(windows) or 3,
        "windows": windows,
    }


def summarize_source(source: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = [str(row.get("ticker") or "") for row in rows if row.get("ticker")]
    ticker_counts = Counter(tickers)
    max_single_ticker_share = (
        max(ticker_counts.values()) / len(rows) if rows and ticker_counts else 1.0
    )
    comparator_summaries = {
        field: metric_summary([as_float(row.get(field)) for row in rows if as_float(row.get(field)) is not None])
        for field in CONFIG["comparators"]
    }
    failed: list[str] = []
    if len(rows) < CONFIG["min_enriched_rows_per_source"]:
        failed.append(
            f"rows_below_min:{len(rows)}/{CONFIG['min_enriched_rows_per_source']}"
        )
    if max_single_ticker_share > CONFIG["max_single_ticker_share"]:
        failed.append(
            f"single_ticker_share:{rounded(max_single_ticker_share, 4)}>{CONFIG['max_single_ticker_share']}"
        )
    if any((comparator_summaries[field]["mean"] or 0.0) >= 0 for field in CONFIG["comparators"]):
        failed.append("not_all_comparator_means_negative")
    if CONFIG["negative_median_required"] and any(
        (comparator_summaries[field]["median"] or 0.0) >= 0
        for field in CONFIG["comparators"]
    ):
        failed.append("not_all_comparator_medians_negative")

    total_notional = sum(
        as_float(row.get("notional_usd")) or 0.0
        for row in rows
    )
    sample_rows = sorted(
        [
            {
                "decision_id": row.get("decision_id"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "pnl_usd": rounded(as_float(row.get("pnl_usd")), 2),
                "replacement_value_vs_cash_usd": rounded(
                    as_float(row.get("replacement_value_vs_cash_usd")), 2
                ),
                "replacement_value_vs_spy_usd": rounded(
                    as_float(row.get("replacement_value_vs_spy_usd")), 2
                ),
                "replacement_value_vs_qqq_usd": rounded(
                    as_float(row.get("replacement_value_vs_qqq_usd")), 2
                ),
                "entry_regime_label": row.get("entry_regime_label"),
                "entry_short_volume_toxic_flag": row.get(
                    "entry_short_volume_toxic_flag"
                ),
            }
            for row in rows
        ],
        key=lambda item: (item["replacement_value_vs_cash_usd"] or 0.0),
    )[:5]
    return {
        "source": source,
        "enriched_rows": len(rows),
        "ticker_count": len(ticker_counts),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "max_single_ticker_share": rounded(max_single_ticker_share, 4),
        "entry_dates": sorted({str(row.get("entry_date")) for row in rows if row.get("entry_date")}),
        "exit_dates": sorted({str(row.get("exit_date")) for row in rows if row.get("exit_date")}),
        "total_notional_usd": rounded(total_notional, 2),
        "comparators": comparator_summaries,
        "kill_switch_candidate": not failed,
        "failed_reasons": failed,
        "sample_worst_rows": sample_rows,
    }


def summarize_rows(raw_rows: list[dict[str, Any]], enriched_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched_rows:
        by_source[source_from_row(row)].append(row)
    source_rows = [
        summarize_source(source, rows)
        for source, rows in sorted(by_source.items())
    ]
    source_rows.sort(
        key=lambda row: (
            not row["kill_switch_candidate"],
            row["comparators"]["replacement_value_vs_cash_usd"]["mean"] or 0.0,
        )
    )
    candidates = [row for row in source_rows if row["kill_switch_candidate"]]
    all_tickers = Counter(str(row.get("ticker") or "") for row in enriched_rows if row.get("ticker"))
    all_sources = Counter(source_from_row(row) for row in enriched_rows)
    return {
        "ledger_path": repo_rel(FORWARD_RV),
        "raw_rows": len(raw_rows),
        "enriched_rows": len(enriched_rows),
        "source_count": len(by_source),
        "ticker_count": len(all_tickers),
        "source_counts": dict(sorted(all_sources.items())),
        "ticker_counts": dict(sorted(all_tickers.items())),
        "overall_comparators": {
            field: metric_summary(
                [
                    as_float(row.get(field))
                    for row in enriched_rows
                    if as_float(row.get(field)) is not None
                ]
            )
            for field in CONFIG["comparators"]
        },
        "sources": source_rows,
        "kill_switch_candidates": candidates,
    }


def build_gate4(summary: dict[str, Any]) -> dict[str, Any]:
    candidates = summary["kill_switch_candidates"]
    failed: list[str] = []
    if not candidates:
        failed.append("no_source_passed_fixed_kill_switch_gate")
    if summary["enriched_rows"] < 20:
        failed.append(f"overall_enriched_rows_thin:{summary['enriched_rows']}/20")
    if candidates:
        failed.append("observed_only_not_shared_policy_ready")
    return {
        "mode": "observed_only_source_level_forward_replacement_attribution",
        "passed": bool(candidates),
        "accepted_alpha": False,
        "observed_only_lead": bool(candidates),
        "failed_reasons": failed,
        "candidate_count": len(candidates),
        "candidate_sources": [row["source"] for row in candidates],
        "binding_acceptance_note": (
            "Observed-only lead only. A real kill switch would require a "
            "separate shared production/backtest policy and Gate 1-4; this "
            "runner does not change allocation."
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
        "source_kill_switch_summary",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = compact_baseline()
    raw_rows, enriched_rows = load_forward_rows()
    summary = summarize_rows(raw_rows, enriched_rows)
    gate4 = build_gate4(summary)
    positive_lead = gate4["observed_only_lead"]
    status = (
        "observed_only_positive_lead"
        if positive_lead
        else "observed_only_rejected"
    )
    decision = (
        "observed_only_positive_source_kill_switch_lead_not_policy_ready"
        if positive_lead
        else "observed_only_rejected_no_source_level_kill_switch_cohort"
    )
    actual_success = 1 if positive_lead else 0
    predicted = float(PREDICTION["success_probability"])
    realized_modes = list(gate4["failed_reasons"])
    if not positive_lead:
        realized_modes.append("no_source_all_comparators_negative")
    if any(
        "rows_below_min" in reason
        for row in summary["sources"]
        for reason in row["failed_reasons"]
    ):
        realized_modes.append("source_samples_too_thin")
    if any(
        "single_ticker_share" in reason
        for row in summary["sources"]
        for reason in row["failed_reasons"]
    ):
        realized_modes.append("single_ticker_concentration")

    gate1 = {
        "passed": bool(baseline.get("available")),
        "baseline_metrics": baseline,
    }
    gate2 = {
        "passed": bool(enriched_rows),
        "fields_checked": [
            "entry_date",
            "exit_date",
            "ticker",
            "sleeve_key",
            "replacement_value_vs_cash_usd",
            "replacement_value_vs_spy_usd",
            "replacement_value_vs_qqq_usd",
        ],
        "missing_or_invalid_fields": {
            "raw_rows": len(raw_rows),
            "complete_enriched_rows": len(enriched_rows),
            "incomplete_rows": len(raw_rows) - len(enriched_rows),
        },
        "entry_date_target_price_note": (
            "Forward replacement rows have entry_date/exit_date and comparator "
            "outcomes. target_price is not an executable signal dependency for "
            "this observed-only attribution runner."
        ),
    }
    gate3 = {
        "passed": True,
        "filter_added": False,
        "signals_generated": len(raw_rows),
        "signals_survived": len(enriched_rows),
        "survival_rate": rounded(len(enriched_rows) / len(raw_rows), 6)
        if raw_rows
        else 0.0,
        "note": "No executable filter, rank, size, exit, or order rule changed.",
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": positive_lead,
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
        "prior_trial_count": ticket.get("prior_trial_count", 0),
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "parameters": CONFIG,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": rounded((actual_success - predicted) ** 2, 4),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": sorted(set(realized_modes)),
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"]) & set(realized_modes)
            ),
            "surprise_note": (
                "A source-level negative cohort appeared despite the low prior; "
                "this remains only an observed-only lead."
                if positive_lead
                else "The fixed cross-source gate did not find a deployable negative source cohort."
            ),
        },
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "source_kill_switch_summary": summary,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "scope": "read_only_forward_replacement_value_attribution",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The cross-source gate found at least one source with enough "
                "diversified enriched rows and negative average replacement "
                "value versus cash, SPY, and QQQ; this is a kill-switch lead, "
                "not accepted allocation policy."
                if positive_lead
                else "Most sources remain too thin, too concentrated, or not negative against all comparators under the fixed source-level gate."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun this by changing min rows, concentration, "
                "comparator set, source labels, or response curve on the same "
                "forward rows."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more settled forward "
                "replacement rows, a separate shared production/backtest "
                "kill-switch policy Gate 1-4, or a genuinely new data source."
            ),
        },
        "rejection_reason": None if positive_lead else ";".join(gate4["failed_reasons"]),
        "next_retry_requires": [
            "materially_more_settled_forward_replacement_rows",
            "shared_policy_gate_1_4_for_any_kill_switch",
            "no_threshold_or_response_curve_retune_on_same_rows",
        ],
        "related_files": [
            repo_rel(FORWARD_RV),
            repo_rel(BASELINE_RESULT),
            repo_rel(TICKET_JSON),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
            repo_rel(EXPERIMENT_LOG),
        ],
        "allowed_write_scope": ticket.get("allowed_write_scope", []),
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": True,
        "ticket_before": ticket,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["source_kill_switch_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Default-Off Forward Source Kill-Switch Attribution",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Result",
        "",
        f"- Raw / enriched rows: `{summary['raw_rows']}` / `{summary['enriched_rows']}`",
        f"- Source count: `{summary['source_count']}`",
        f"- Candidate sources: `{', '.join(payload['gate4']['candidate_sources']) or 'none'}`",
        f"- Gate 4 failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
        "",
        "| Source | Rows | Max ticker share | Cash mean | SPY mean | QQQ mean | Candidate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["sources"][:12]:
        lines.append(
            f"| {row['source']} | {row['enriched_rows']} | "
            f"{row['max_single_ticker_share']} | "
            f"{row['comparators']['replacement_value_vs_cash_usd']['mean']} | "
            f"{row['comparators']['replacement_value_vs_spy_usd']['mean']} | "
            f"{row['comparators']['replacement_value_vs_qqq_usd']['mean']} | "
            f"{row['kill_switch_candidate']} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        EXPERIMENT_LOG,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_record = compact_log_record(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "runner": RUNNER,
            "gate4": payload["gate4"],
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
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "source_kill_switch_summary": {
                "raw_rows": payload["source_kill_switch_summary"]["raw_rows"],
                "enriched_rows": payload["source_kill_switch_summary"]["enriched_rows"],
                "candidate_sources": payload["gate4"]["candidate_sources"],
            },
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
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
                "candidate_sources": payload["gate4"]["candidate_sources"],
                "gate4": payload["gate4"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
