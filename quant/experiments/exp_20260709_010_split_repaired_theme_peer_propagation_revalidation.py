"""exp-20260709-010: revalidate split-repaired theme-peer propagation.

Read-only alpha revalidation. exp-20260709-008 repaired split-discontinuous
OHLCV warehouse rows for KLAC and CRWD and explicitly named exp-20260702-017
and exp-20260702-018 as contaminated consumers. This runner reuses those two
fixed attribution bundles unchanged, recomputes them on the repaired warehouse,
and compares the resulting metrics against the original artifacts.

No event class, theme edge, horizon, threshold, ranking, sizing, notional, or
response rule changes. No production/backtest behavior changes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    text = str(entry)
    if text not in sys.path:
        sys.path.insert(0, text)

from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260709-010"
OWNER = "alpha-explore"
SLUG = "split_repaired_theme_peer_propagation_revalidation"
RUNNER = f"quant/experiments/exp_20260709_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260709_010_{SLUG}.json"
ROWS_IPO = DATA_DIR / "revalidated_ipo_rows.jsonl"
ROWS_425 = DATA_DIR / "revalidated_sec_425_rows.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

OLD_IPO_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260702-017"
    / "exp_20260702_017_ipo_theme_propagation.json"
)
OLD_IPO_ROWS = OLD_IPO_ARTIFACT.parent / "propagation_rows.jsonl"
OLD_425_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260702-018"
    / "exp_20260702_018_sec_425_merger_theme_peer_propagation.json"
)
OLD_425_ROWS = OLD_425_ARTIFACT.parent / "propagation_rows.jsonl"

MODULES = {
    "ipo": REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260702_017_ipo_theme_propagation.py",
    "sec_425": REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260702_018_sec_425_merger_theme_peer_propagation.py",
}
IMPACTED_TICKERS = {"KLAC", "CRWD"}

HYPOTHESIS = (
    "After the accepted warehouse split-adjustment repair, the previously "
    "contaminated IPO and SEC 425 theme-peer propagation attribution verdicts "
    "must be re-run on repaired KLAC/CRWD OHLCV to see whether the original "
    "no-edge conclusion changes without any event, horizon, threshold, "
    "ranking, sizing, or response retune."
)
SINGLE_CAUSAL_VARIABLE = (
    "split_repaired_theme_peer_propagation_verdict_revalidation_v1"
)
CAUSAL_COMPONENTS = [
    "reuse exp-20260702-017 fixed IPO theme-peer bundle",
    "reuse exp-20260702-018 fixed SEC 425 theme-peer bundle",
    "repaired OHLCV warehouse only",
    "pre/post artifact delta",
    "read-only no strategy change",
]
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260709_010_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/revalidated_ipo_rows.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/revalidated_sec_425_rows.jsonl",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
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


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"exp_20260709_010_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_report(report: dict[str, Any]) -> dict[str, Any]:
    per_window = {}
    for name, window in (report.get("per_window") or {}).items():
        per_window[name] = {
            "rows": window.get("rows"),
            "median_delta_10d_bp": window.get("median_delta_10d_bp"),
            "mean_delta_10d_bp": window.get("mean_delta_10d_bp"),
            "median_delta_5d_bp": window.get("median_delta_5d_bp"),
            "positive_share": window.get("positive_share"),
            "top_ticker": window.get("top_ticker"),
            "top_ticker_share": window.get("top_ticker_share"),
        }
    return {
        "settled_rows": report.get("settled_rows"),
        "deduped_rows": report.get("deduped_rows"),
        "pooled_rows": report.get("pooled_rows"),
        "pooled_median_delta_10d_bp": report.get("pooled_median_delta_10d_bp"),
        "sign_consistent": report.get("sign_consistent"),
        "rows_threshold_ok": report.get("rows_threshold_ok"),
        "pooled_delta_threshold_ok": report.get("pooled_delta_threshold_ok"),
        "observed_only_lead": report.get("observed_only_lead"),
        "per_window": per_window,
    }


def numeric_delta(new_value: Any, old_value: Any) -> float | int | None:
    if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)):
        delta = new_value - old_value
        return round(delta, 6) if isinstance(delta, float) else delta
    return None


def report_delta(current: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "settled_rows": numeric_delta(
            current.get("settled_rows"), old.get("settled_rows")
        ),
        "deduped_rows": numeric_delta(
            current.get("deduped_rows"), old.get("deduped_rows")
        ),
        "pooled_rows": numeric_delta(current.get("pooled_rows"), old.get("pooled_rows")),
        "pooled_median_delta_10d_bp": numeric_delta(
            current.get("pooled_median_delta_10d_bp"),
            old.get("pooled_median_delta_10d_bp"),
        ),
        "observed_only_lead_changed": current.get("observed_only_lead")
        != old.get("observed_only_lead"),
        "per_window": {},
    }
    for name, cur_window in (current.get("per_window") or {}).items():
        old_window = (old.get("per_window") or {}).get(name, {})
        result["per_window"][name] = {
            key: numeric_delta(cur_window.get(key), old_window.get(key))
            for key in (
                "rows",
                "median_delta_10d_bp",
                "mean_delta_10d_bp",
                "median_delta_5d_bp",
                "positive_share",
                "top_ticker_share",
            )
        }
        result["per_window"][name]["top_ticker_changed"] = (
            cur_window.get("top_ticker") != old_window.get("top_ticker")
        )
    return result


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("ticker") or "").upper(), str(row.get("entry_date") or ""))


def compare_rows(
    current_rows: list[dict[str, Any]], old_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    current_by_key = {row_key(row): row for row in current_rows}
    old_by_key = {row_key(row): row for row in old_rows}
    common = sorted(set(current_by_key) & set(old_by_key))
    current_only = sorted(set(current_by_key) - set(old_by_key))
    old_only = sorted(set(old_by_key) - set(current_by_key))

    metric_changed = []
    impacted_keys = []
    for key in common:
        ticker, _entry = key
        if ticker in IMPACTED_TICKERS:
            impacted_keys.append(key)
        cur = current_by_key[key]
        old = old_by_key[key]
        changes: dict[str, float] = {}
        for field in ("excess_10d", "excess_5d"):
            cur_value = cur.get(field)
            old_value = old.get(field)
            if isinstance(cur_value, (int, float)) and isinstance(
                old_value, (int, float)
            ):
                diff = float(cur_value) - float(old_value)
                if abs(diff) > 0.000001:
                    changes[field] = round(diff, 8)
        if changes:
            metric_changed.append(
                {
                    "ticker": key[0],
                    "entry_date": key[1],
                    "changes": changes,
                    "is_impacted_ticker": key[0] in IMPACTED_TICKERS,
                }
            )

    return {
        "old_rows": len(old_rows),
        "current_rows": len(current_rows),
        "common_rows": len(common),
        "current_only_rows": len(current_only),
        "old_only_rows": len(old_only),
        "impacted_ticker_common_rows": len(impacted_keys),
        "metric_changed_common_rows": len(metric_changed),
        "metric_changed_impacted_rows": sum(
            1 for row in metric_changed if row["is_impacted_ticker"]
        ),
        "sample_metric_changes": metric_changed[:12],
        "sample_current_only": [{"ticker": t, "entry_date": d} for t, d in current_only[:8]],
        "sample_old_only": [{"ticker": t, "entry_date": d} for t, d in old_only[:8]],
    }


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def revalidate() -> dict[str, Any]:
    ipo_module = load_module("ipo", MODULES["ipo"])
    sec_425_module = load_module("sec_425", MODULES["sec_425"])

    current_ipo_report, current_ipo_rows = ipo_module.run_attribution()
    current_425_report, current_425_rows = sec_425_module.analyze()

    old_ipo_payload = read_json(OLD_IPO_ARTIFACT)
    old_425_payload = read_json(OLD_425_ARTIFACT)
    old_ipo_report = old_ipo_payload["audit"]
    old_425_report = old_425_payload["audit"]
    old_ipo_rows = read_jsonl(OLD_IPO_ROWS)
    old_425_rows = read_jsonl(OLD_425_ROWS)

    cohorts = {
        "ipo_theme_peer": {
            "prior_experiment": "exp-20260702-017",
            "old_artifact": repo_rel(OLD_IPO_ARTIFACT),
            "old_rows": repo_rel(OLD_IPO_ROWS),
            "module": repo_rel(MODULES["ipo"]),
            "before": clean_report(old_ipo_report),
            "after": clean_report(current_ipo_report),
            "delta": report_delta(
                clean_report(current_ipo_report), clean_report(old_ipo_report)
            ),
            "row_delta": compare_rows(current_ipo_rows, old_ipo_rows),
        },
        "sec_425_theme_peer": {
            "prior_experiment": "exp-20260702-018",
            "old_artifact": repo_rel(OLD_425_ARTIFACT),
            "old_rows": repo_rel(OLD_425_ROWS),
            "module": repo_rel(MODULES["sec_425"]),
            "before": clean_report(old_425_report),
            "after": clean_report(current_425_report),
            "delta": report_delta(
                clean_report(current_425_report), clean_report(old_425_report)
            ),
            "row_delta": compare_rows(current_425_rows, old_425_rows),
        },
    }
    return {
        "cohorts": cohorts,
        "current_rows": {
            "ipo_theme_peer": current_ipo_rows,
            "sec_425_theme_peer": current_425_rows,
        },
    }


def verdict(cohorts: dict[str, Any]) -> tuple[str, str, list[str], bool]:
    any_lead = any(
        bool(cohort["after"].get("observed_only_lead"))
        for cohort in cohorts.values()
    )
    any_verdict_changed = any(
        bool(cohort["delta"].get("observed_only_lead_changed"))
        for cohort in cohorts.values()
    )
    changed_metric_rows = sum(
        int(cohort["row_delta"].get("metric_changed_common_rows") or 0)
        for cohort in cohorts.values()
    )
    if any_lead:
        return (
            "observed_only_positive_split_repair_changed_theme_peer_lead_not_promoted",
            "observed_only_positive",
            [],
            True,
        )
    if any_verdict_changed:
        return (
            "observed_only_rejected_split_repair_verdict_changed_but_no_lead",
            "observed_only_rejected",
            ["repaired_metrics_changed_but_no_fixed_bundle_observed_only_lead"],
            False,
        )
    reasons = ["no_prior_theme_peer_verdict_changed", "no_current_observed_only_lead"]
    if changed_metric_rows == 0:
        reasons.append("no_row_level_metric_changes_detected")
    else:
        reasons.append("row_level_metrics_changed_but_not_verdict")
    return (
        "observed_only_rejected_split_repair_no_alpha_verdict_change",
        "observed_only_rejected",
        reasons,
        False,
    )


def calibration(prediction: dict[str, Any], success: bool, reasons: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    reason_text = " ".join(reasons)
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    hits = [
        mode
        for mode in predicted_modes
        if (
            ("too small" in mode and "verdict" in reason_text)
            or ("sign" in mode and "lead" in reason_text)
            or ("not enough" in mode and "no_current" in reason_text)
        )
    ]
    return {
        "predicted_success_probability": probability,
        "actual_success": int(success),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": reasons,
        "predicted_failure_modes_hit": hits,
        "surprise_note": (
            "Split repair changed a theme-peer propagation verdict."
            if success
            else "Split repair did not change the no-edge theme-peer verdicts."
        ),
    }


def build_payload(revalidation: dict[str, Any]) -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    cohorts = revalidation["cohorts"]
    decision, status, reasons, success = verdict(cohorts)
    prediction = dict(ticket.get("prediction") or {})
    baseline = load_baseline_metrics()
    total_metric_changed = sum(
        int(cohort["row_delta"].get("metric_changed_common_rows") or 0)
        for cohort in cohorts.values()
    )
    impacted_metric_changed = sum(
        int(cohort["row_delta"].get("metric_changed_impacted_rows") or 0)
        for cohort in cohorts.values()
    )
    why = (
        "Re-running the fixed IPO and SEC 425 theme-peer attribution bundles "
        "on the split-repaired warehouse did not create an observed-only lead "
        "or change either prior no-edge verdict. The repaired rows are valid "
        "measurement hygiene, but not new alpha evidence for this relation "
        "surface."
        if not success
        else "At least one fixed theme-peer attribution bundle became an "
        "observed-only lead after the split-repaired warehouse recomputation. "
        "This is not promoted because no shared helper or daily path changed."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": success,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "observed_only_attribution",
        "implementation_mode": "read_only_revalidation",
        "mechanism_family": "production_visible_sec_corporate_event_stream",
        "trial_family": "split_repaired_theme_peer_propagation_revalidation",
        "trial_variant_id": "split_repaired_ipo_425_theme_peer_revalidation_v1",
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": "none_read_only_revalidation",
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": [
            "exp-20260702-017",
            "exp-20260702-018",
            "exp-20260709-008",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "repaired_warehouse_ohlcv_split_adjustment",
        "new_evidence_axis": (
            "Accepted exp-20260709-008 repaired split-discontinuous OHLCV "
            "values for KLAC/CRWD rows that the prior IPO/425 theme-peer "
            "artifacts consumed; this reruns the identical fixed bundles and "
            "measures artifact deltas, not a new row slice or threshold."
        ),
        "prediction": prediction,
        "calibration": calibration(prediction, success, reasons),
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "strategy_behavior_changed": False,
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "row_level_metric_changed_rows": total_metric_changed,
            "impacted_ticker_metric_changed_rows": impacted_metric_changed,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "Novelty override accepted because exp-20260709-008 repaired "
                "the exact KLAC/CRWD OHLCV rows consumed by the old artifacts."
            ),
            "3_single_policy_bundle": (
                "Re-run the unchanged exp-20260702-017 IPO and "
                "exp-20260702-018 SEC 425 theme-peer attribution bundles on "
                "the repaired warehouse; compare artifact deltas only."
            ),
            "4_success_failure_standard": (
                "Positive only if the unchanged fixed-bundle observed-only "
                "lead criteria now pass or the prior verdict changes because "
                "of repaired OHLCV. Otherwise reject as no alpha verdict change."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "revalidation": cohorts,
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": True,
            "fields": [
                "event_class",
                "form_type",
                "filed_date",
                "theme",
                "ticker",
                "entry_date",
                "Open/Close warehouse bars",
            ],
            "entry_date": "validated by imported fixed bundles",
            "target_price_scope": "not_applicable_observed_only_fixed_horizon",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter, rank, or sizing rule was added.",
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
        },
        "gate4": {
            "mode": "observed_only_revalidation",
            "passed": False,
            "observed_only_lead": success,
            "failed_reasons": reasons,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "parity_note": "Read-only revalidation; no production or backtest behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not re-run IPO/425 theme-peer propagation again on the "
                "same repaired warehouse, and do not re-slice by theme, "
                "keyword, horizon, entry lag, density, ticker status, top-N, "
                "hold, cooldown, notional, or response shape."
            ),
            "new_evidence_required": (
                "A valid future retry needs richer deal/economic provenance "
                "such as priced-deal terms, cash/stock consideration, bidder "
                "or target role, amendment/termination trajectory, PIT SIC "
                "repair, materially more closed forward rows under a shared "
                "helper, or a new non-SEC relation data source."
            ),
        },
        "next_retry_requires": [
            "richer deal economics or entity relation provenance",
            "materially more closed forward rows under a shared helper",
            "no further same-warehouse revalidation IDs for this contamination",
        ],
        "rejection_reason": ";".join(reasons),
        "related_files": [
            repo_rel(MODULES["ipo"]),
            repo_rel(MODULES["sec_425"]),
            repo_rel(OLD_IPO_ARTIFACT),
            repo_rel(OLD_425_ARTIFACT),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": [RUNNER_COMMAND],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": True,
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "hypothesis",
        "alpha_hypothesis",
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
        "pre_run_questions",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "rejection_reason",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    record = {key: payload[key] for key in keys}
    record["audit_summary"] = {
        name: {
            "prior_experiment": cohort["prior_experiment"],
            "old_lead": cohort["before"].get("observed_only_lead"),
            "current_lead": cohort["after"].get("observed_only_lead"),
            "pooled_median_delta_10d_bp_old": cohort["before"].get(
                "pooled_median_delta_10d_bp"
            ),
            "pooled_median_delta_10d_bp_current": cohort["after"].get(
                "pooled_median_delta_10d_bp"
            ),
            "row_delta": cohort["row_delta"],
            "per_window_delta": cohort["delta"].get("per_window"),
        }
        for name, cohort in payload["revalidation"].items()
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: split-repaired theme-peer revalidation",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        "- Production behavior changed: no",
        f"- Row metric changes: `{payload['delta_metrics']['row_level_metric_changed_rows']}`",
        f"- Impacted-ticker metric changes: `{payload['delta_metrics']['impacted_ticker_metric_changed_rows']}`",
        "",
        "## Cohorts",
        "",
    ]
    for name, cohort in payload["revalidation"].items():
        before = cohort["before"]
        after = cohort["after"]
        delta = cohort["delta"]
        row_delta = cohort["row_delta"]
        lines += [
            f"### {name}",
            "",
            f"- prior: `{cohort['prior_experiment']}`",
            f"- observed_only_lead: `{before.get('observed_only_lead')}` -> `{after.get('observed_only_lead')}`",
            f"- pooled median delta 10d bp: `{before.get('pooled_median_delta_10d_bp')}` -> `{after.get('pooled_median_delta_10d_bp')}` (delta `{delta.get('pooled_median_delta_10d_bp')}`)",
            f"- settled rows: `{before.get('settled_rows')}` -> `{after.get('settled_rows')}`",
            f"- common impacted rows: `{row_delta.get('impacted_ticker_common_rows')}`",
            f"- metric-changed rows: `{row_delta.get('metric_changed_common_rows')}`",
            "",
        ]
        for window_name, window_delta in (delta.get("per_window") or {}).items():
            lines.append(
                f"- `{window_name}` median delta change: "
                f"`{window_delta.get('median_delta_10d_bp')}` bp; "
                f"rows `{window_delta.get('rows')}`"
            )
        lines.append("")
    lines += [
        "## Reflection",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Reproduction",
        "",
        f"```powershell\n{RUNNER_COMMAND}\n```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        ROWS_IPO,
        ROWS_425,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        OLD_IPO_ARTIFACT,
        OLD_IPO_ROWS,
        OLD_425_ARTIFACT,
        OLD_425_ROWS,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": CHANGED_FILES,
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    write_json(OUT_JSON, payload)
    write_jsonl(ROWS_IPO, rows["ipo_theme_peer"])
    write_jsonl(ROWS_425, rows["sec_425_theme_peer"])
    write_json(LOG_JSON, compact_log(payload))
    write_text(CARD_MD, build_card(payload))

    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    revalidation = revalidate()
    rows = revalidation.pop("current_rows")
    payload = build_payload(revalidation)
    persist(payload, rows)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "row_level_metric_changed_rows": payload["delta_metrics"][
                    "row_level_metric_changed_rows"
                ],
                "impacted_ticker_metric_changed_rows": payload["delta_metrics"][
                    "impacted_ticker_metric_changed_rows"
                ],
                "cohorts": {
                    name: {
                        "old_lead": cohort["before"].get("observed_only_lead"),
                        "current_lead": cohort["after"].get("observed_only_lead"),
                        "pooled_old": cohort["before"].get(
                            "pooled_median_delta_10d_bp"
                        ),
                        "pooled_current": cohort["after"].get(
                            "pooled_median_delta_10d_bp"
                        ),
                        "metric_changed_rows": cohort["row_delta"].get(
                            "metric_changed_common_rows"
                        ),
                    }
                    for name, cohort in payload["revalidation"].items()
                },
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
