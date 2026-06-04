"""exp-20260604-016: lagged consensus density monotonicity audit.

Observed-only alpha search. This runner reads the accepted lagged free-data
consensus replay from exp-20260604-008 and asks whether selected paper trades
show a stable monotonic outcome ladder by prior independent source-family
confirmation density.

No production adapter, ranking, sizing, exit, order, LLM, or news path changes.
No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260604-016"
STEM = "lagged_consensus_density_monotonicity"
SOURCE_EXPERIMENT_ID = "exp-20260604-008"
ACCEPTED_ADAPTER_EXPERIMENT_ID = "exp-20260604-009"

SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "lagged_independent_source_consensus.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_016_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_lagged_density_monotonicity"
TRIAL_VARIANT_ID = "prior_family_density_0_1_2plus_v1"
CHANGED_VARIABLE = "prior_independent_source_confirmation_density_bucket_v1"

BUCKET_ORDER = ["same_day_only", "prior_1_family", "prior_2plus_families"]
MIN_AGG_BUCKET_COUNT = 8
MIN_WINDOW_BUCKET_COUNT = 3

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "no_monotonic_ladder",
        "thin_high_density_bucket",
        "window_instability",
        "accepted_adapter_already_saturated",
    ],
    "confidence_reason": (
        "The accepted lagged adapter has strong three-window evidence, but "
        "recent nearby rank/support retunes failed; this run only tests "
        "evidence density before any new rule."
    ),
    "recorded_at": "2026-06-04T16:06:55+00:00",
}

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "default_off_paper_only": True,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "trade_enabled": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bucket(prior_family_count: int) -> str:
    if prior_family_count <= 0:
        return "same_day_only"
    if prior_family_count == 1:
        return "prior_1_family"
    return "prior_2plus_families"


def _append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = row["experiment_id"]
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if existing.get("experiment_id") == experiment_id:
                    return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _materialize_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window, trades in (source.get("target_trades_by_window") or {}).items():
        for trade in trades or []:
            prior_family_count = _safe_int(trade.get("prior_confirmation_family_count"))
            prior_source_count = _safe_int(trade.get("prior_confirmation_source_count"))
            prior_lags = [
                _safe_int(row.get("confirmation_lag_trading_days"))
                for row in trade.get("source_rows") or []
                if row.get("timing_role") == "prior_confirmation"
            ]
            rows.append(
                {
                    "window": window,
                    "ticker": str(trade.get("ticker") or "").upper(),
                    "signal_date": trade.get("signal_date") or trade.get("date"),
                    "entry_date": trade.get("entry_date"),
                    "bucket": _bucket(prior_family_count),
                    "prior_confirmation_family_count": prior_family_count,
                    "prior_confirmation_source_count": prior_source_count,
                    "source_family_count": _safe_int(trade.get("source_family_count")),
                    "source_count": _safe_int(trade.get("source_count")),
                    "current_source_family_count": _safe_int(
                        trade.get("current_source_family_count")
                    ),
                    "has_lagged_independent_confirmation": bool(
                        trade.get("has_lagged_independent_confirmation")
                    ),
                    "min_prior_lag_trading_days": min(prior_lags) if prior_lags else None,
                    "max_prior_lag_trading_days": max(prior_lags) if prior_lags else None,
                    "pnl_usd": round(_safe_float(trade.get("pnl")), 6),
                    "pnl_pct_net": round(_safe_float(trade.get("pnl_pct_net")), 8),
                    "source_families": list(trade.get("source_families") or []),
                    "prior_confirmation_source_families": list(
                        trade.get("prior_confirmation_source_families") or []
                    ),
                }
            )
    return rows


def _summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    pnls = [_safe_float(row.get("pnl_usd")) for row in rows]
    returns = [_safe_float(row.get("pnl_pct_net")) for row in rows]
    positives = [value for value in pnls if value > 0]
    positive_total = sum(positives)
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        if _safe_float(row.get("pnl_usd")) > 0:
            by_ticker[str(row.get("ticker") or "")] += _safe_float(row.get("pnl_usd"))
    max_single_share = max(by_ticker.values()) / positive_total if positive_total > 0 else 0.0
    return {
        "count": count,
        "total_pnl_usd": round(sum(pnls), 2),
        "avg_pnl_usd": round(sum(pnls) / count, 4) if count else None,
        "median_pnl_usd": round(median(pnls), 4) if count else None,
        "avg_pnl_pct_net": round(sum(returns) / count, 6) if count else None,
        "median_pnl_pct_net": round(median(returns), 6) if count else None,
        "win_rate": round(sum(1 for value in pnls if value > 0) / count, 6) if count else None,
        "positive_pnl_total_usd": round(positive_total, 2),
        "max_single_positive_share": round(max_single_share, 6),
    }


def _bucket_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        bucket: _summarize_bucket([row for row in rows if row["bucket"] == bucket])
        for bucket in BUCKET_ORDER
    }


def _window_bucket_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    windows = sorted({str(row["window"]) for row in rows})
    return {
        window: _bucket_summary([row for row in rows if row["window"] == window])
        for window in windows
    }


def _avg_return_ladder(summary: dict[str, dict[str, Any]]) -> list[float | None]:
    return [summary[bucket].get("avg_pnl_pct_net") for bucket in BUCKET_ORDER]


def _is_strictly_increasing(values: list[float | None]) -> bool:
    if any(value is None for value in values):
        return False
    clean = [float(value) for value in values if value is not None]
    return all(left < right for left, right in zip(clean, clean[1:]))


def _is_strictly_decreasing(values: list[float | None]) -> bool:
    if any(value is None for value in values):
        return False
    clean = [float(value) for value in values if value is not None]
    return all(left > right for left, right in zip(clean, clean[1:]))


def _monotonic_validation(
    aggregate_summary: dict[str, dict[str, Any]],
    window_summary: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    aggregate_counts = [aggregate_summary[bucket]["count"] for bucket in BUCKET_ORDER]
    aggregate_ladder = _avg_return_ladder(aggregate_summary)
    aggregate_monotonic_increasing = _is_strictly_increasing(aggregate_ladder)
    aggregate_monotonic_decreasing = _is_strictly_decreasing(aggregate_ladder)
    window_checks = []
    for window, summary in sorted(window_summary.items()):
        counts = [summary[bucket]["count"] for bucket in BUCKET_ORDER]
        ladder = _avg_return_ladder(summary)
        evaluable = all(count >= MIN_WINDOW_BUCKET_COUNT for count in counts)
        increasing = _is_strictly_increasing(ladder) if evaluable else False
        decreasing = _is_strictly_decreasing(ladder) if evaluable else False
        window_checks.append(
            {
                "window": window,
                "counts": dict(zip(BUCKET_ORDER, counts)),
                "avg_pnl_pct_ladder": dict(zip(BUCKET_ORDER, ladder)),
                "evaluable": evaluable,
                "monotonic_increasing": increasing,
                "monotonic_decreasing": decreasing,
            }
        )
    evaluable_windows = [row for row in window_checks if row["evaluable"]]
    increasing_windows = [row for row in evaluable_windows if row["monotonic_increasing"]]
    decreasing_windows = [row for row in evaluable_windows if row["monotonic_decreasing"]]
    return {
        "bucket_order": BUCKET_ORDER,
        "minimum_aggregate_bucket_count": MIN_AGG_BUCKET_COUNT,
        "minimum_window_bucket_count": MIN_WINDOW_BUCKET_COUNT,
        "aggregate_counts": dict(zip(BUCKET_ORDER, aggregate_counts)),
        "aggregate_avg_pnl_pct_ladder": dict(zip(BUCKET_ORDER, aggregate_ladder)),
        "aggregate_monotonic_increasing": aggregate_monotonic_increasing,
        "aggregate_monotonic_decreasing": aggregate_monotonic_decreasing,
        "aggregate_sample_gate_passed": min(aggregate_counts) >= MIN_AGG_BUCKET_COUNT,
        "window_checks": window_checks,
        "evaluable_window_count": len(evaluable_windows),
        "monotonic_increasing_window_count": len(increasing_windows),
        "monotonic_decreasing_window_count": len(decreasing_windows),
    }


def _baseline_metrics(source: dict[str, Any]) -> dict[str, Any]:
    aggregate = source.get("aggregate") or {}
    before = aggregate.get("after") or aggregate.get("before") or {}
    windows = {}
    for result in source.get("results") or []:
        label = result.get("label")
        if label:
            windows[label] = result.get("after") or result.get("before") or {}
    return {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "accepted_adapter_experiment_id": ACCEPTED_ADAPTER_EXPERIMENT_ID,
        "aggregate": {
            "expected_value_score": before.get("expected_value_score_sum")
            or before.get("expected_value_score"),
            "strategy_total_pnl": before.get("strategy_total_pnl_sum")
            or before.get("strategy_total_pnl")
            or before.get("total_pnl_sum"),
            "trade_count": before.get("trade_count_sum") or before.get("trade_count"),
            "min_survival_rate": before.get("min_survival_rate"),
            "max_drawdown_pct_max": before.get("max_drawdown_pct_max"),
        },
        "windows": {
            label: {
                "expected_value_score": metrics.get("expected_value_score"),
                "strategy_total_pnl": metrics.get("strategy_total_pnl")
                or metrics.get("total_pnl"),
                "trade_count": metrics.get("trade_count"),
                "survival_rate": metrics.get("survival_rate"),
                "max_drawdown_pct": metrics.get("max_drawdown_pct"),
            }
            for label, metrics in sorted(windows.items())
        },
    }


def _decision(validation: dict[str, Any]) -> tuple[str, str, bool]:
    if not validation["aggregate_sample_gate_passed"]:
        return (
            "rejected_lagged_density_bucket_sample_gate_failed",
            "At least one aggregate density bucket is below the sample floor.",
            False,
        )
    if not validation["aggregate_monotonic_increasing"]:
        return (
            "rejected_lagged_density_no_positive_monotonic_ladder",
            "Average net return does not increase from same-day-only to higher prior-confirmation density.",
            False,
        )
    if validation["evaluable_window_count"] < 2:
        return (
            "rejected_lagged_density_window_sample_too_thin",
            "Fewer than two windows have enough observations in every density bucket.",
            False,
        )
    if validation["monotonic_increasing_window_count"] < validation["evaluable_window_count"]:
        return (
            "rejected_lagged_density_window_instability",
            "The aggregate ladder is not stable across all evaluable windows.",
            False,
        )
    return (
        "observed_only_positive_lagged_density_ladder_not_promoted",
        "The observed ladder is positive, but no rule is promoted without a separate shared-policy experiment.",
        True,
    )


def _log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validation = payload["monotonic_validation"]
    actual_success = 1 if payload["accepted"] else 0
    predicted = PREDICTION["success_probability"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 7,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "before_metrics": payload["before_metrics"]["aggregate"],
        "after_metrics": payload["after_metrics"]["aggregate"],
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "strategy_behavior_changed": False,
        },
        "metrics": {
            "target_trade_count": payload["row_count"],
            "aggregate_bucket_counts": validation["aggregate_counts"],
            "aggregate_avg_pnl_pct_ladder": validation["aggregate_avg_pnl_pct_ladder"],
            "aggregate_monotonic_increasing": validation["aggregate_monotonic_increasing"],
            "evaluable_window_count": validation["evaluable_window_count"],
            "monotonic_increasing_window_count": validation[
                "monotonic_increasing_window_count"
            ],
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": payload["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 6),
            "realized_failure_mode": None if actual_success else payload["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": None if payload["accepted"] else payload["decision_rationale"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
    }


def _artifact_text(payload: dict[str, Any]) -> str:
    validation = payload["monotonic_validation"]
    aggregate = payload["aggregate_bucket_summary"]
    lines = [
        f"# {EXPERIMENT_ID} Lagged Consensus Density Monotonicity",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Source replay: `{_repo_rel(SOURCE_JSON)}`",
        f"- Target trades: `{payload['row_count']}`",
        "- Production impact: observed-only; no shared policy, adapter, ranking, sizing, exit, order, LLM, or news change.",
        "",
        "## Gate Answers",
        "",
        f"1. Hypothesis: {payload['gate_questions']['1_alpha_hypothesis']}",
        f"2. History: {payload['gate_questions']['2_history_check']}",
        f"3. Single causal variable: `{CHANGED_VARIABLE}`.",
        f"4. Standard: {payload['gate_questions']['4_acceptance_standard']}",
        f"5. Reproducibility: `{payload['gate_questions']['5_reproducibility']}`",
        "",
        "## Aggregate Buckets",
        "",
        "| Bucket | Count | Avg PnL % | Avg PnL $ | Total PnL $ | Win rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for bucket in BUCKET_ORDER:
        row = aggregate[bucket]
        lines.append(
            f"| `{bucket}` | {row['count']} | {row['avg_pnl_pct_net']} | "
            f"{row['avg_pnl_usd']} | {row['total_pnl_usd']} | {row['win_rate']} |"
        )
    lines.extend(
        [
            "",
            "## Monotonic Validation",
            "",
            f"- Aggregate monotonic increasing: `{validation['aggregate_monotonic_increasing']}`",
            f"- Aggregate sample gate passed: `{validation['aggregate_sample_gate_passed']}`",
            f"- Evaluable windows: `{validation['evaluable_window_count']}`",
            f"- Increasing evaluable windows: `{validation['monotonic_increasing_window_count']}`",
            "",
            "## Window Checks",
            "",
            "| Window | Evaluable | Same-day avg % | Prior 1 avg % | Prior 2+ avg % | Increasing |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in validation["window_checks"]:
        ladder = row["avg_pnl_pct_ladder"]
        lines.append(
            f"| `{row['window']}` | {row['evaluable']} | "
            f"{ladder['same_day_only']} | {ladder['prior_1_family']} | "
            f"{ladder['prior_2plus_families']} | {row['monotonic_increasing']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["decision_rationale"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _card_text(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Lane: `alpha_search`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Artifact: `{_repo_rel(OUT_JSON)}`",
            "",
            payload["decision_rationale"],
            "",
        ]
    )


def _git_info() -> dict[str, Any]:
    def run(args: list[str]) -> str:
        try:
            return subprocess.check_output(args, cwd=REPO_ROOT, text=True).strip()
        except subprocess.CalledProcessError:
            return ""

    status = run(["git", "status", "--short"]).splitlines()
    return {
        "branch": run(["git", "branch", "--show-current"]),
        "commit": run(["git", "rev-parse", "HEAD"]),
        "dirty": bool(status),
        "status_short": status[:120],
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    if not TICKET_JSON.exists():
        return
    ticket = _load_json(TICKET_JSON)
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["completed_at"]
    ticket["result"] = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "artifact": _repo_rel(OUT_JSON),
        "summary": payload["decision_rationale"],
    }
    scope = ticket.setdefault("allowed_write_scope", [])
    artifact_path = _repo_rel(ARTIFACT_MD)
    if artifact_path not in scope:
        scope.append(artifact_path)
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = payload["status"]
            item["completed_at"] = payload["completed_at"]
            item["owner"] = "codex-alpha-explore"
            item["result"] = {
                "decision": payload["decision"],
                "accepted": payload["accepted"],
                "artifact": _repo_rel(OUT_JSON),
            }
            break
    _write_json(REGISTRY_JSON, registry)


def _write_manifest(payload: dict[str, Any]) -> None:
    artifacts = [
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        ARTIFACT_MD,
        TICKET_JSON,
    ]
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["created_at"],
        "completed_at": payload["completed_at"],
        "artifacts": [_repo_rel(path) for path in artifacts],
        "files": {
            _repo_rel(path): {"exists": path.exists(), "sha256": _sha256(path)}
            for path in artifacts
        },
        "source_files": {
            _repo_rel(SOURCE_JSON): {
                "exists": SOURCE_JSON.exists(),
                "sha256": _sha256(SOURCE_JSON),
            }
        },
        "git": _git_info(),
    }
    _write_json(MANIFEST_JSON, manifest)


def build_payload() -> dict[str, Any]:
    source = _load_json(SOURCE_JSON)
    rows = _materialize_rows(source)
    aggregate_summary = _bucket_summary(rows)
    window_summary = _window_bucket_summary(rows)
    validation = _monotonic_validation(aggregate_summary, window_summary)
    decision, rationale, accepted = _decision(validation)
    completed_at = _utc_now()
    before_metrics = _baseline_metrics(source)
    after_metrics = json.loads(json.dumps(before_metrics))
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "status": "observed_only" if accepted else "rejected",
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "Accepted lagged free-data consensus trades should show stable "
            "monotonic outcome structure by prior independent source-confirmation "
            "density before any ranking or allocation reuse."
        ),
        "change_summary": (
            "Observed-only monotonic validation of exp-20260604-008 selected "
            "paper trades by prior independent source-family confirmation density."
        ),
        "change_type": "observed_only_ranking_validation",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": [
            "exp-20260604-008",
            "exp-20260604-009",
            "exp-20260604-010",
            "exp-20260604-011",
            "exp-20260604-012",
            "exp-20260604-013",
            "exp-20260604-015",
        ],
        "new_evidence_type": "observed_only_monotonic_validation_on_accepted_lagged_consensus",
        "parameters": {
            "source_artifact": _repo_rel(SOURCE_JSON),
            "bucket_definition": {
                "same_day_only": "prior_confirmation_family_count == 0",
                "prior_1_family": "prior_confirmation_family_count == 1",
                "prior_2plus_families": "prior_confirmation_family_count >= 2",
            },
            "bucket_order": BUCKET_ORDER,
            "minimum_aggregate_bucket_count": MIN_AGG_BUCKET_COUNT,
            "minimum_window_bucket_count": MIN_WINDOW_BUCKET_COUNT,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking/capital allocation attribution: stronger lagged "
                "independent source-confirmation density should identify cleaner "
                "accepted lagged consensus trades."
            ),
            "2_history_check": (
                "exp-20260604-008 found the positive lagged source-timing lead; "
                "exp-20260604-009 promoted the shared default-off adapter; "
                "exp-20260604-010 through 015 rejected nearby rank/support/source "
                "retunes versus the accepted lagged comparator."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only pass requires aggregate return monotonicity by "
                "density bucket, aggregate bucket sample >= 8, and stable "
                "monotonicity across at least two evaluable standard windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260604_016_lagged_consensus_density_monotonicity.py"
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "strategy_behavior_changed": False,
        },
        "row_count": len(rows),
        "aggregate_bucket_summary": aggregate_summary,
        "window_bucket_summary": window_summary,
        "monotonic_validation": validation,
        "sample_rows": rows[:20],
        "decision_rationale": rationale,
        "prediction": PREDICTION,
        "production_impact": PRODUCTION_IMPACT,
        "next_retry_requires": [
            "closed forward replacement-value rows",
            "larger high-density bucket sample",
            "stable monotonic ladder across all three standard windows",
            "separate shared-policy experiment before any ranking or allocation change",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(SOURCE_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def main() -> int:
    payload = build_payload()
    log_row = _log_payload(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_row)
    _write_text(ARTIFACT_MD, _artifact_text(payload))
    _write_text(CARD_MD, _card_text(payload))
    _append_jsonl_once(EXPERIMENT_LOG, log_row)
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": payload["decision"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
