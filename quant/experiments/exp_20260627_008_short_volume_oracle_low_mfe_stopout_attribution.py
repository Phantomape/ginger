"""exp-20260627-008: short-volume attribution on oracle entry-quality losses.

Observed-only alpha attribution. The single question is whether the PIT
Moomoo daily ``short_volume_ratio`` percentile is enriched in the exact
fixed-entry oracle / loss-taxonomy cohort that the oracle compass identifies as
the remaining clean headroom: low-MFE stopouts and weak initial follow-through
losses.

This runner changes no shared policy, entry, exit, ranking, sizing, order,
daily snapshot, paper sleeve state, watchlist, or LLM boundary. A positive
result can only justify future forward logging or a materially different
borrow/flow evidence axis. It does not reopen the rejected exp-20260625-019
clean-flow candidate-pool gate.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
EXPERIMENTS_ROOT = REPO_ROOT / "quant" / "experiments"
for entry in (REPO_ROOT, SCRIPTS_ROOT, EXPERIMENTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260625_018_short_volume_informed_flow_attribution as sv_base  # noqa: E402


EXPERIMENT_ID = "exp-20260627-008"
OWNER = "alpha-explore"
SLUG = "short_volume_oracle_low_mfe_stopout_attribution"
RUNNER = f"quant/experiments/exp_20260627_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ORACLE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-003"
    / "exp_20260623_003_fixed_entry_exit_oracle_regret_cluster.json"
)
LOSS_TAXONOMY_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260511-102"
    / "exp_20260511_102_accepted_stack_oracle_loss_taxonomy.json"
)
EXP019_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260625-019.json"
ORACLE_COMPASS = REPO_ROOT / "docs" / "oracle_regret_compass.md"

HYPOTHESIS = (
    "Observed-only attribution: PIT moomoo short_volume_ratio should be higher "
    "on fixed-entry oracle low-MFE stopout and failed-followthrough loss rows "
    "than on other accepted-stack trades, explaining weak-tape immediate "
    "entry-quality regret without changing strategy behavior."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "observed_only_oracle_loss_cluster_attribution"
MECHANISM_FAMILY = "oracle_entry_quality_regret_attribution"
TRIAL_FAMILY = "moomoo_short_volume_oracle_low_mfe_stopout_attribution"
TRIAL_VARIANT_ID = "oracle_low_mfe_stopout_short_volume_percentile_v1"
CHANGED_VARIABLE = "moomoo_short_volume_oracle_low_mfe_stopout_attribution_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_oracle_loss_cluster_attribution"
NEW_EVIDENCE_AXIS = (
    "New gate shape: oracle/loss-taxonomy cluster enrichment attribution on "
    "fixed accepted-stack trades, not a short-volume threshold, clean-flow "
    "candidate-pool gate, forward-row reslice, top-N, hold-day, notional, or "
    "allocator retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-003",
    "exp-20260511-102",
    "exp-20260625-018",
    "exp-20260625-019",
    "exp-20260625-023",
]
CAUSAL_COMPONENTS = [
    "fixed-entry exit oracle rows",
    "accepted-stack loss taxonomy rows",
    "PIT short_volume_ratio percentile join",
    "loss-cluster enrichment test",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.32,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "oracle_rows_do_not_join_to_short_volume",
        "short_volume_not_enriched_in_loss_cluster",
        "signal_already_untradable_after_exp019",
        "old_thin_only_effect",
    ],
    "confidence_reason": (
        "Oracle compass isolated remaining regret to weak-tape immediate "
        "entry-quality failures, and prior PIT short-volume attribution was "
        "sign-correct plus placebo-clean; the main risk is that the specific "
        "oracle low-MFE stopout cluster is too small or not enriched, and "
        "exp019 already blocks direct promotion."
    ),
    "recorded_at": "2026-06-27T07:14:21+00:00",
}
CONFIG = {
    "min_joined_rows": 30,
    "min_target_joined_rows": 6,
    "min_target_mean_percentile_edge": 0.15,
    "min_target_q4_q5_share_edge": 0.20,
    "min_directional_windows_with_target_n_ge_2": 2,
    "toxic_percentile_floor": 0.80,
    "q4_q5_percentile_floor": 0.60,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    encoded = json.dumps(record, sort_keys=True)
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(json.dumps(existing, sort_keys=True))
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def r4(value: Any) -> float | None:
    number = as_float(value)
    return None if number is None else round(number, 4)


def sha256(path: Path) -> str | None:
    return sv_base.sha256(path)


def trade_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("ticker") or "").upper(),
            str(row.get("entry_date") or "")[:10],
            str(row.get("window") or ""),
        ]
    )


def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pcts = [row["short_volume_percentile"] for row in rows if row.get("short_volume_percentile") is not None]
    pnls = [as_float(row.get("actual_pnl")) for row in rows]
    pnls = [value for value in pnls if value is not None]
    if not pcts:
        return {
            "n": 0,
            "mean_percentile": None,
            "median_percentile": None,
            "q4_q5_share": None,
            "q5_share": None,
            "avg_actual_pnl": None,
            "total_actual_pnl": None,
        }
    return {
        "n": len(pcts),
        "mean_percentile": round(sum(pcts) / len(pcts), 6),
        "median_percentile": round(float(median(pcts)), 6),
        "q4_q5_share": round(sum(1 for pct in pcts if pct >= CONFIG["q4_q5_percentile_floor"]) / len(pcts), 4),
        "q5_share": round(sum(1 for pct in pcts if pct >= CONFIG["toxic_percentile_floor"]) / len(pcts), 4),
        "avg_actual_pnl": None if not pnls else round(sum(pnls) / len(pnls), 2),
        "total_actual_pnl": None if not pnls else round(sum(pnls), 2),
    }


def load_short_volume_percentiles() -> tuple[dict[str, tuple[list[str], list[float | None]]], dict[str, Any]]:
    by_ticker, audit = sv_base.load_short_volume()
    return sv_base.build_percentile_index(by_ticker), audit


def load_oracle_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = read_json(ORACLE_ARTIFACT, {}) or {}
    rows = payload.get("attribution", {}).get("sample_rows", [])
    if not isinstance(rows, list):
        rows = []
    return rows, {
        "source": repo_rel(ORACLE_ARTIFACT),
        "exists": ORACLE_ARTIFACT.exists(),
        "n_rows_reported": payload.get("attribution", {}).get("n_rows"),
        "rows_loaded": len(rows),
        "decision": payload.get("decision"),
        "status": payload.get("status"),
    }


def load_loss_taxonomy_labels() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payload = read_json(LOSS_TAXONOMY_ARTIFACT, {}) or {}
    rows = payload.get("bad_trades", [])
    out: dict[str, dict[str, Any]] = {}
    label_counts: Counter[str] = Counter()
    if isinstance(rows, list):
        for row in rows:
            labels = [str(item) for item in row.get("oracle_labels", [])]
            for label in labels:
                label_counts[label] += 1
            out[trade_key(row)] = {
                "loss_taxonomy_joined": True,
                "loss_taxonomy_labels": labels,
                "loss_taxonomy_pnl": r4(row.get("pnl")),
                "loss_taxonomy_mfe_pct": r4(row.get("mfe_pct")),
                "loss_taxonomy_mae_pct": r4(row.get("mae_pct")),
            }
    return out, {
        "source": repo_rel(LOSS_TAXONOMY_ARTIFACT),
        "exists": LOSS_TAXONOMY_ARTIFACT.exists(),
        "bad_rows_loaded": len(rows) if isinstance(rows, list) else 0,
        "label_counts": dict(sorted(label_counts.items())),
        "decision": payload.get("decision"),
        "status": payload.get("status"),
    }


def target_reasons(row: dict[str, Any]) -> list[str]:
    labels = set(row.get("loss_taxonomy_labels") or [])
    reasons: list[str] = []
    if "oracle_low_mfe_stopout" in labels:
        reasons.append("loss_taxonomy_oracle_low_mfe_stopout")
    if "weak_initial_follow_through" in labels:
        reasons.append("loss_taxonomy_weak_initial_follow_through")
    if (
        row.get("exit_reason") == "stop"
        and row.get("actual_outcome_bucket") == "actual_loss_with_positive_oracle"
        and row.get("oracle_timing_bucket") == "day0_1"
    ):
        reasons.append("fixed_entry_stop_loss_positive_oracle_day0_1")
    return reasons


def build_joined_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    oracle_rows, oracle_audit = load_oracle_rows()
    labels_by_key, loss_audit = load_loss_taxonomy_labels()
    pct_index, sv_audit = load_short_volume_percentiles()
    joined: list[dict[str, Any]] = []
    missing_percentile = 0
    for row in oracle_rows:
        merged = dict(row)
        merged.update(labels_by_key.get(trade_key(row), {"loss_taxonomy_joined": False, "loss_taxonomy_labels": []}))
        ticker = str(merged.get("ticker") or "").upper()
        entry_date = str(merged.get("entry_date") or "")[:10]
        pct = sv_base.percentile_asof(pct_index, ticker, entry_date)
        if pct is None:
            missing_percentile += 1
            continue
        reasons = target_reasons(merged)
        merged.update(
            {
                "short_volume_percentile": round(float(pct), 6),
                "short_volume_quintile": sv_base.quintile(float(pct)) + 1,
                "target_oracle_low_mfe_failed_followthrough": bool(reasons),
                "target_reasons": reasons,
                "trade_key_compact": trade_key(row),
            }
        )
        joined.append(merged)
    audit = {
        "oracle": oracle_audit,
        "loss_taxonomy": loss_audit,
        "short_volume": sv_audit,
        "oracle_rows_missing_short_volume_percentile": missing_percentile,
        "joined_rows": len(joined),
    }
    return joined, audit


def summarize_attribution(rows: list[dict[str, Any]], source_audit: dict[str, Any]) -> dict[str, Any]:
    target = [row for row in rows if row["target_oracle_low_mfe_failed_followthrough"]]
    other = [row for row in rows if not row["target_oracle_low_mfe_failed_followthrough"]]
    by_window: dict[str, Any] = {}
    directional_windows = 0
    directional_windows_with_target_n_ge_2 = 0
    for window in ["old_thin", "mid_weak", "late_strong"]:
        target_window = [row for row in target if row.get("window") == window]
        other_window = [row for row in other if row.get("window") == window]
        target_stats = stats(target_window)
        other_stats = stats(other_window)
        mean_edge = None
        q4_q5_edge = None
        if target_stats["mean_percentile"] is not None and other_stats["mean_percentile"] is not None:
            mean_edge = round(target_stats["mean_percentile"] - other_stats["mean_percentile"], 6)
        if target_stats["q4_q5_share"] is not None and other_stats["q4_q5_share"] is not None:
            q4_q5_edge = round(target_stats["q4_q5_share"] - other_stats["q4_q5_share"], 6)
        direction = bool(mean_edge is not None and mean_edge > 0)
        if direction:
            directional_windows += 1
            if target_stats["n"] >= 2:
                directional_windows_with_target_n_ge_2 += 1
        by_window[window] = {
            "target": target_stats,
            "other": other_stats,
            "target_minus_other_mean_percentile": mean_edge,
            "target_minus_other_q4_q5_share": q4_q5_edge,
            "direction_target_higher": direction,
        }

    target_stats = stats(target)
    other_stats = stats(other)
    pooled_mean_edge = None
    pooled_q4_q5_edge = None
    if target_stats["mean_percentile"] is not None and other_stats["mean_percentile"] is not None:
        pooled_mean_edge = round(target_stats["mean_percentile"] - other_stats["mean_percentile"], 6)
    if target_stats["q4_q5_share"] is not None and other_stats["q4_q5_share"] is not None:
        pooled_q4_q5_edge = round(target_stats["q4_q5_share"] - other_stats["q4_q5_share"], 6)

    reason_counts = Counter(reason for row in target for reason in row["target_reasons"])
    by_ticker = Counter(row["ticker"] for row in target)
    return {
        "source_audit": source_audit,
        "pooled": {
            "target": target_stats,
            "other": other_stats,
            "target_minus_other_mean_percentile": pooled_mean_edge,
            "target_minus_other_q4_q5_share": pooled_q4_q5_edge,
            "target_reason_counts": dict(sorted(reason_counts.items())),
            "target_ticker_counts": dict(sorted(by_ticker.items())),
        },
        "by_window": by_window,
        "directional_windows": directional_windows,
        "directional_windows_with_target_n_ge_2": directional_windows_with_target_n_ge_2,
        "target_rows_sample": [
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "window": row.get("window"),
                "actual_pnl": r4(row.get("actual_pnl")),
                "exit_reason": row.get("exit_reason"),
                "actual_outcome_bucket": row.get("actual_outcome_bucket"),
                "oracle_timing_bucket": row.get("oracle_timing_bucket"),
                "short_volume_percentile": row.get("short_volume_percentile"),
                "short_volume_quintile": row.get("short_volume_quintile"),
                "target_reasons": row.get("target_reasons"),
            }
            for row in sorted(target, key=lambda item: item.get("short_volume_percentile", 0), reverse=True)[:12]
        ],
    }


def evaluate_gate4(attribution: dict[str, Any]) -> dict[str, Any]:
    pooled = attribution["pooled"]
    target = pooled["target"]
    other = pooled["other"]
    failed: list[str] = []
    if attribution["source_audit"]["joined_rows"] < CONFIG["min_joined_rows"]:
        failed.append("joined_rows_below_floor")
    if target["n"] < CONFIG["min_target_joined_rows"]:
        failed.append("target_joined_rows_below_floor")
    mean_edge = pooled["target_minus_other_mean_percentile"]
    q4_q5_edge = pooled["target_minus_other_q4_q5_share"]
    if mean_edge is None or mean_edge < CONFIG["min_target_mean_percentile_edge"]:
        failed.append("target_mean_short_volume_percentile_not_enriched")
    if q4_q5_edge is None or q4_q5_edge < CONFIG["min_target_q4_q5_share_edge"]:
        failed.append("target_q4_q5_share_not_enriched")
    if (
        attribution["directional_windows_with_target_n_ge_2"]
        < CONFIG["min_directional_windows_with_target_n_ge_2"]
    ):
        failed.append("window_direction_not_robust")
    exp019_decision = (read_json(EXP019_LOG, {}) or {}).get("decision")
    observed_only_lead = not failed
    return {
        "acceptance_rule": (
            "Observed-only lead requires >=30 joined oracle rows, >=6 joined target "
            "low-MFE/failed-followthrough rows, target mean PIT short-volume "
            "percentile at least 15pp above other fixed-entry trades, target "
            "Q4/Q5 share at least 20pp above other trades, and target-higher "
            "direction in at least two windows with target n>=2. Passing this "
            "does not promote a strategy because exp-20260625-019 already "
            "rejected the tradable clean-flow gate."
        ),
        "observed_only_lead": observed_only_lead,
        "passed": observed_only_lead,
        "decision": (
            "observed_only_positive_oracle_short_volume_loss_enrichment_not_promoted"
            if observed_only_lead
            else "observed_only_rejected_no_oracle_short_volume_loss_enrichment"
        ),
        "failed_reasons": failed,
        "promotion_blockers": [
            "exp-20260625-019 rejected the shared clean-flow candidate-pool gate",
            "no strategy, paper helper, daily snapshot, order, ranking, sizing, or exit changed",
            "future work needs borrow/utilization/loan-availability evidence or new forward rows",
        ],
        "exp019_decision": exp019_decision,
        "pooled_target_minus_other_mean_percentile": mean_edge,
        "pooled_target_minus_other_q4_q5_share": q4_q5_edge,
        "directional_windows_with_target_n_ge_2": attribution[
            "directional_windows_with_target_n_ge_2"
        ],
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    summary = payload.get("summary", payload)
    windows = summary.get("windows") or payload.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": 7.8941,
        "total_pnl": 234850.99,
        "trade_count": 61,
        "signals_generated": 164,
        "signals_survived": 135,
        "survival_rate": 0.8232,
        "window_count": 3,
        "source_windows_found": len(windows) if isinstance(windows, list) else None,
    }


def calibration(gate4: dict[str, Any]) -> dict[str, Any]:
    actual = 1 if gate4["observed_only_lead"] else 0
    predicted = PREDICTION["success_probability"]
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual,
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 4),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_mode": "; ".join(gate4["failed_reasons"]) or None,
        "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
        "surprise_note": (
            "The specific oracle low-MFE / failed-followthrough target cohort "
            "did enrich on PIT short-volume percentiles, but direct promotion "
            "remains blocked by exp019."
            if actual
            else "The oracle target cohort did not show robust short-volume "
            "enrichment, so short_volume_ratio does not explain this fixed "
            "entry-quality regret cluster."
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
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "attribution",
        "production_impact",
        "post_run_reflection",
        "reproduction_commands",
        "related_files",
        "anti_js",
    ]
    return {key: payload[key] for key in keys if key in payload}


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    joined, source_audit = build_joined_rows()
    attribution = summarize_attribution(joined, source_audit)
    gate4 = evaluate_gate4(attribution)
    baseline = baseline_metrics()
    status = (
        "observed_only_positive_lead"
        if gate4["observed_only_lead"]
        else "observed_only_rejected"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
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
        "prediction": PREDICTION,
        "calibration": calibration(gate4),
        "parameters": {
            "config": CONFIG,
            "short_volume_source": repo_rel(sv_base.SHORT_VOLUME_ROWS),
            "oracle_artifact": repo_rel(ORACLE_ARTIFACT),
            "loss_taxonomy_artifact": repo_rel(LOSS_TAXONOMY_ARTIFACT),
            "pit_rule": (
                "For a trade entry_date, use the most recent short_volume_ratio "
                "percentile formed from activity_date strictly before entry_date; "
                "each percentile itself is expanding and strictly prior within ticker."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted the reservation; nearest score 0.0585.",
                "exp-20260625-018": "Observed sign-correct broad short-volume lead.",
                "exp-20260625-019": "Rejected tradable clean-flow gate; direct promotion remains blocked.",
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One read-only enrichment test: fixed oracle/loss-taxonomy target "
                "cohort joined to PIT short-volume percentiles."
            ),
            "4_success_failure_standard": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
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
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                "oracle sample_rows ticker/entry_date/window",
                "loss taxonomy oracle_labels",
                "moomoo short_volume_ratio",
                "activity_date strictly before entry_date",
            ],
            "target_price": {
                "available": False,
                "reason": "Observed-only attribution; no executable target or order is scheduled.",
            },
            "source_audit": attribution["source_audit"],
        },
        "gate3": {
            "passed": True,
            "note": "No executable filter was added; survival is unchanged.",
            "signals_generated": attribution["source_audit"]["joined_rows"],
            "signals_survived": attribution["source_audit"]["joined_rows"],
            "strategy_filter_added": False,
            "survival_rate": 1.0,
        },
        "gate4": gate4,
        "attribution": attribution,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": "Read-only attribution over existing oracle/loss/short-volume artifacts.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "PIT short-volume enriched in the fixed oracle weak-entry loss "
                "cluster, which means the field may explain part of the "
                "entry-quality regret, but it does not overcome exp019's "
                "rejected tradable gate."
                if gate4["observed_only_lead"]
                else "PIT short-volume did not robustly enrich in the exact "
                "oracle low-MFE / failed-followthrough loss cohort, so the "
                "remaining oracle regret likely needs another ex-ante state, "
                "news, sector-cluster, borrow, or flow field."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune short_volume_ratio thresholds, quintiles, "
                "lookbacks, top-N, hold days, notional, or allocator rank on "
                "these frozen windows; exp019 remains the binding clean-flow "
                "promotion failure."
            ),
            "new_evidence_required": (
                "Valid next evidence needs PIT borrow fee/utilization/loan "
                "availability, a non-short-volume ex-ante event/state/sector "
                "label for the same oracle loss cluster, or materially more "
                "closed forward rows tagged at entry."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(ORACLE_ARTIFACT),
            repo_rel(LOSS_TAXONOMY_ARTIFACT),
            repo_rel(sv_base.SHORT_VOLUME_ROWS),
            repo_rel(EXP019_LOG),
            repo_rel(ORACLE_COMPASS),
            repo_rel(BASELINE_RESULT),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number * 100:.1f}%"


def build_card(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]
    rows = [
        "| Scope | target n | target mean pct | other mean pct | edge | target Q4/Q5 | other Q4/Q5 |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            "| pooled | {tn} | {tm} | {om} | {edge} | {tq} | {oq} |".format(
                tn=pooled["target"]["n"],
                tm=pct(pooled["target"]["mean_percentile"]),
                om=pct(pooled["other"]["mean_percentile"]),
                edge=pct(pooled["target_minus_other_mean_percentile"]),
                tq=pct(pooled["target"]["q4_q5_share"]),
                oq=pct(pooled["other"]["q4_q5_share"]),
            )
        ),
    ]
    for window, item in payload["attribution"]["by_window"].items():
        rows.append(
            "| {window} | {tn} | {tm} | {om} | {edge} | {tq} | {oq} |".format(
                window=window,
                tn=item["target"]["n"],
                tm=pct(item["target"]["mean_percentile"]),
                om=pct(item["other"]["mean_percentile"]),
                edge=pct(item["target_minus_other_mean_percentile"]),
                tq=pct(item["target"]["q4_q5_share"]),
                oq=pct(item["other"]["q4_q5_share"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: short-volume oracle low-MFE stopout attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Enrichment",
            "",
            *rows,
            "",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Promotion blockers: `{', '.join(payload['gate4']['promotion_blockers'])}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    existing = read_json(TICKET_JSON, {}) or {}
    existing.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "owner": OWNER,
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": {
                "observed_only_lead": payload["observed_only_lead"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        }
    )
    return existing


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        ORACLE_ARTIFACT,
        LOSS_TAXONOMY_ARTIFACT,
        sv_base.SHORT_VOLUME_ROWS,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "decision": payload["decision"],
        "status": payload["status"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in paths
        },
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, build_ticket(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
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
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
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
                "joined_rows": payload["attribution"]["source_audit"]["joined_rows"],
                "target_rows": payload["attribution"]["pooled"]["target"]["n"],
                "pooled_mean_percentile_edge": payload["gate4"][
                    "pooled_target_minus_other_mean_percentile"
                ],
                "pooled_q4_q5_share_edge": payload["gate4"][
                    "pooled_target_minus_other_q4_q5_share"
                ],
                "directional_windows_with_target_n_ge_2": payload["gate4"][
                    "directional_windows_with_target_n_ge_2"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
