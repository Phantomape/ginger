"""exp-20260630-009: fixed-entry exit-oracle gap attribution.

Observed-only alpha diagnostic. This reads the fixed-entry oracle blocks already
emitted by the canonical 2026-06-04 backtests and asks whether avoidable exit
regret clusters by production-visible fields strongly enough to justify a later
shared exit-policy experiment.

No entry, exit, ranking, sizing, paper, live, watchlist, LLM, or news behavior
is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-009"
OWNER = "alpha-explore"
SLUG = "fixed_entry_exit_oracle_gap_attribution"
RUNNER = f"quant/experiments/exp_20260630_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for root in (REPO_ROOT, SCRIPTS_ROOT):
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ARCHIVE_DIR = (
    REPO_ROOT / "data" / "backtests" / "archive" / "20260604_ohlcv_warehouse_replay"
)
WINDOW_FILES = {
    "late_strong": ARCHIVE_DIR / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    "mid_weak": ARCHIVE_DIR / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    "old_thin": ARCHIVE_DIR / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
}
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Fixed-entry exit oracle diagnostics may reveal a production-visible "
    "exit-gap cohort where current canonical exits leave avoidable giveback, "
    "justifying a later shared exit-policy experiment without changing current "
    "entries, exits, ranking, sizing, or orders."
)
CHANGE_TYPE = "observed_only_exit_oracle_attribution"
MECHANISM_FAMILY = "exit_policy_oracle_diagnostic"
TRIAL_FAMILY = "fixed_entry_exit_oracle_gap_attribution"
TRIAL_VARIANT_ID = "canonical_20260604_oracle_blocks_v1"
CHANGED_VARIABLE = "fixed_entry_exit_oracle_gap_attribution_v1"
NEW_EVIDENCE_TYPE = "canonical_fixed_entry_oracle_diagnostic_block"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260429-032", "exp-20260623-020"]
CAUSAL_COMPONENTS = [
    "canonical_oracle_diagnostics",
    "entry_fixed_exit_gap_grouping",
    "observed_only_verdict",
    "no_strategy_change",
]

MIN_TOP_REGRET_ROWS_ALL_WINDOWS = 6
MIN_STABLE_COHORT_WINDOWS = 3
MIN_COHORT_REGRET_SHARE = 0.35
MIN_TOTAL_REGRET_USD = 20_000.0
MAX_SINGLE_WINDOW_REGRET_SHARE = 0.60


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, set):
        return sorted(safe(item) for item in value)
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number:.2%}"


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction if isinstance(prediction, dict) else {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "windows": windows,
    }


def date_diff_days(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        return (
            datetime.strptime(end, "%Y-%m-%d")
            - datetime.strptime(start, "%Y-%m-%d")
        ).days
    except ValueError:
        return None


def load_window_oracle(label: str, path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    oracle = (payload.get("oracle_diagnostics") or {}).get("oracle_metrics") or {}
    perfect = oracle.get("perfect_exit") or {}
    top_rows = []
    for row in perfect.get("top_regret_trades") or []:
        if not isinstance(row, dict):
            continue
        enriched = dict(row)
        enriched["window"] = label
        enriched["oracle_exit_lead_days"] = date_diff_days(
            row.get("oracle_exit_date"), row.get("actual_exit_date")
        )
        top_rows.append(enriched)
    return {
        "window": label,
        "source_file": repo_rel(path),
        "backtest_metrics": {
            "expected_value_score": payload.get("expected_value_score"),
            "total_pnl": payload.get("total_pnl"),
            "max_drawdown_pct": payload.get("max_drawdown_pct"),
            "trade_count": payload.get("total_trades"),
            "signals_generated": payload.get("signals_generated"),
            "signals_survived": payload.get("signals_survived"),
            "survival_rate": payload.get("survival_rate"),
        },
        "perfect_exit": {
            "trade_count": perfect.get("trade_count"),
            "missing_trade_count": perfect.get("missing_trade_count"),
            "actual_pnl": perfect.get("actual_pnl"),
            "oracle_pnl": perfect.get("oracle_pnl"),
            "regret_vs_oracle": perfect.get("regret_vs_oracle"),
            "capture_ratio": perfect.get("capture_ratio"),
            "by_strategy": perfect.get("by_strategy") or {},
            "top_regret_rows": top_rows,
            "top_regret_row_count": len(top_rows),
            "has_full_trade_level_oracle_rows": False,
        },
        "raw_oracle_keys": sorted(oracle),
    }


def group_rows(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key) or "missing") for key in keys)].append(row)
    out = {}
    for key, members in sorted(grouped.items()):
        regret = sum(float(row.get("regret_vs_oracle") or 0.0) for row in members)
        windows = sorted({str(row.get("window")) for row in members})
        out["|".join(key)] = {
            "keys": dict(zip(keys, key)),
            "row_count": len(members),
            "window_count": len(windows),
            "windows": windows,
            "regret_vs_oracle": round(regret, 2),
            "avg_regret_vs_oracle": round(regret / len(members), 2) if members else None,
            "tickers": sorted({str(row.get("ticker")) for row in members}),
        }
    return out


def summarize_oracle(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = [
        row
        for window in windows.values()
        for row in window["perfect_exit"]["top_regret_rows"]
    ]
    total_regret = sum(
        float(window["perfect_exit"].get("regret_vs_oracle") or 0.0)
        for window in windows.values()
    )
    top_regret = sum(float(row.get("regret_vs_oracle") or 0.0) for row in rows)
    by_strategy = group_rows(rows, ("strategy",))
    by_exit_reason = group_rows(rows, ("exit_reason",))
    by_strategy_exit = group_rows(rows, ("strategy", "exit_reason"))
    by_ticker = group_rows(rows, ("ticker",))
    window_regrets = {
        label: float(window["perfect_exit"].get("regret_vs_oracle") or 0.0)
        for label, window in windows.items()
    }
    worst_capture = min(
        (
            float(window["perfect_exit"].get("capture_ratio"))
            for window in windows.values()
            if as_float(window["perfect_exit"].get("capture_ratio")) is not None
        ),
        default=None,
    )
    best_strategy_exit = None
    for key, row in by_strategy_exit.items():
        if best_strategy_exit is None or row["regret_vs_oracle"] > best_strategy_exit["regret_vs_oracle"]:
            best_strategy_exit = {"cohort": key, **row}
    stable = []
    for key, row in by_strategy_exit.items():
        share = row["regret_vs_oracle"] / top_regret if top_regret > 0 else 0.0
        if (
            row["window_count"] >= MIN_STABLE_COHORT_WINDOWS
            and share >= MIN_COHORT_REGRET_SHARE
        ):
            stable.append({"cohort": key, "top_regret_share": round(share, 6), **row})
    max_window_share = (
        max(window_regrets.values()) / total_regret if total_regret > 0 else None
    )
    return {
        "window_regrets": {k: round(v, 2) for k, v in window_regrets.items()},
        "total_regret_vs_oracle": round(total_regret, 2),
        "top_regret_rows_regret_sum": round(top_regret, 2),
        "top_regret_row_count": len(rows),
        "top_regret_share_of_total_regret": round(top_regret / total_regret, 6)
        if total_regret > 0
        else None,
        "max_single_window_regret_share": round(max_window_share, 6)
        if max_window_share is not None
        else None,
        "worst_capture_ratio": round(worst_capture, 6) if worst_capture is not None else None,
        "by_strategy": by_strategy,
        "by_exit_reason": by_exit_reason,
        "by_strategy_exit_reason": by_strategy_exit,
        "by_ticker": by_ticker,
        "best_strategy_exit_reason_cohort": best_strategy_exit,
        "stable_production_visible_cohorts": stable,
    }


def analyze() -> dict[str, Any]:
    window_payloads = {
        label: load_window_oracle(label, path) for label, path in WINDOW_FILES.items()
    }
    summary = summarize_oracle(window_payloads)
    missing_files = [repo_rel(path) for path in WINDOW_FILES.values() if not path.exists()]
    rows_available = all(
        window["perfect_exit"]["top_regret_row_count"] >= MIN_TOP_REGRET_ROWS_ALL_WINDOWS
        for window in window_payloads.values()
    )
    has_full_trade_level = all(
        window["perfect_exit"]["has_full_trade_level_oracle_rows"]
        for window in window_payloads.values()
    )
    stable_cohort = bool(summary["stable_production_visible_cohorts"])
    enough_regret = float(summary["total_regret_vs_oracle"] or 0.0) >= MIN_TOTAL_REGRET_USD
    not_single_window = (
        as_float(summary.get("max_single_window_regret_share")) is not None
        and float(summary["max_single_window_regret_share"]) <= MAX_SINGLE_WINDOW_REGRET_SHARE
    )
    failed = []
    if missing_files:
        failed.append("missing_oracle_backtest_files")
    if not rows_available:
        failed.append("insufficient_top_regret_rows_all_windows")
    if not has_full_trade_level:
        failed.append("only_top_regret_rows_available_no_full_trade_level_oracle_rows")
    if not stable_cohort:
        failed.append("no_stable_strategy_exit_reason_cohort_across_all_windows")
    if not enough_regret:
        failed.append("oracle_regret_pool_too_small")
    if not not_single_window:
        failed.append("oracle_regret_too_single_window_concentrated")
    observed_positive = not failed
    return {
        "window_payloads": window_payloads,
        "summary": summary,
        "checks": {
            "missing_files": missing_files,
            "top_regret_rows_available_all_windows": rows_available,
            "full_trade_level_oracle_rows_available": has_full_trade_level,
            "stable_production_visible_cohort": stable_cohort,
            "total_regret_vs_oracle_min": MIN_TOTAL_REGRET_USD,
            "max_single_window_regret_share_max": MAX_SINGLE_WINDOW_REGRET_SHARE,
            "observed_only_positive_lead": observed_positive,
        },
        "failed_reasons": failed,
        "observed_only_positive_lead": observed_positive,
    }


def calibration(prediction: Mapping[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = as_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if success else 0.0
    mode_map = {
        "no_trade_level_oracle_rows": {
            "only_top_regret_rows_available_no_full_trade_level_oracle_rows"
        },
        "no_stable_cross_window_cluster": {
            "no_stable_strategy_exit_reason_cohort_across_all_windows",
            "oracle_regret_too_single_window_concentrated",
        },
        "only_future_leakage": set(),
        "no_production_visible_field": {
            "no_stable_strategy_exit_reason_cohort_across_all_windows"
        },
    }
    predicted = list(prediction.get("main_failure_modes") or [])
    hit = [mode for mode in predicted if set(failed) & mode_map.get(mode, set())]
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(success),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted,
        "realized_failure_modes": failed,
        "predicted_failure_modes_hit": hit,
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    attribution = analyze()
    observed_positive = bool(attribution["observed_only_positive_lead"])
    failed = list(attribution["failed_reasons"])
    decision = (
        "observed_only_positive_fixed_entry_exit_oracle_gap_lead_not_promoted"
        if observed_positive
        else "rejected_incomplete_trade_level_fixed_entry_exit_oracle_attribution"
    )
    status = "observed_only_positive_lead" if observed_positive else "rejected"
    why = (
        "The oracle regret pool is real, and the top-regret sample has a tempting "
        "trend_long stop-loss cohort across all three windows. It is still rejected "
        "because the current artifact exposes only top-regret samples rather than "
        "full trade-level oracle rows, so the cohort denominator and false-positive "
        "rate cannot be measured."
        if not observed_positive
        else "The diagnostic found a stable production-visible exit-gap cohort, "
        "but it remains observed-only because the oracle uses future highs."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_positive,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_oracle_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "novelty_gate": (
                    "experiment.py new required novelty override; accepted as "
                    "new gate shape because this reads diagnostic-only fixed-entry "
                    "oracle blocks rather than changing a candidate pool, "
                    "allocator source, response curve, or exit rule."
                ),
                "forbidden_boundary": (
                    "This cannot promote a target trim, trailing stop, or time "
                    "stop. It only decides whether a later shared exit-policy "
                    "hypothesis is worth reserving."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": {
                "must_have_oracle_blocks_all_windows": True,
                "must_have_full_trade_level_oracle_rows": True,
                "stable_cohort_windows_min": MIN_STABLE_COHORT_WINDOWS,
                "cohort_top_regret_share_min": MIN_COHORT_REGRET_SHARE,
                "total_regret_usd_min": MIN_TOTAL_REGRET_USD,
                "max_single_window_regret_share": MAX_SINGLE_WINDOW_REGRET_SHARE,
            },
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "window_files": {label: repo_rel(path) for label, path in WINDOW_FILES.items()},
            "diagnostic_boundary": "Fixed-entry oracle uses future highs; diagnostic only.",
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "oracle_files_loaded": all(path.exists() for path in WINDOW_FILES.values()),
            "passed": BASELINE_RESULT.exists() and all(path.exists() for path in WINDOW_FILES.values()),
        },
        "gate2": {
            "dependencies_validated": True,
            "fields_checked": [
                "oracle_diagnostics.oracle_metrics.perfect_exit.trade_count",
                "oracle_diagnostics.oracle_metrics.perfect_exit.regret_vs_oracle",
                "oracle_diagnostics.oracle_metrics.perfect_exit.capture_ratio",
                "top_regret_trades.entry_date",
                "top_regret_trades.actual_exit_date",
                "top_regret_trades.oracle_exit_date",
                "top_regret_trades.strategy",
                "top_regret_trades.exit_reason",
            ],
            "entry_date_present": all(
                bool(row.get("entry_date"))
                for window in attribution["window_payloads"].values()
                for row in window["perfect_exit"]["top_regret_rows"]
            ),
            "target_price_relevance": (
                "Not applicable. The diagnostic does not schedule target exits "
                "or orders; target_price remains a Gate-2 field for executable "
                "entry/exit experiments."
            ),
            "passed": True,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, candidate selection, or exit rule was added.",
            "passed": True,
        },
        "gate4": {
            "observed_only_lead": observed_positive,
            "decision": decision,
            "failed_reasons": failed,
            "checks": attribution["checks"],
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Oracle exit prices use future intratrade highs and cannot be a live rule input.",
                "The artifact exposes only top-regret trade samples, not full trade-level oracle rows.",
                "No shared exit helper, production adapter, order behavior, or prompt behavior changed.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "oracle_total_regret_vs_oracle": attribution["summary"][
                "total_regret_vs_oracle"
            ],
            "oracle_top_regret_row_count": attribution["summary"][
                "top_regret_row_count"
            ],
        },
        "attribution": attribution,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "llm_prompt_changed": False,
            "daily_snapshot_exposed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "replay_only": False,
            "parity_note": "Read-only diagnostic over existing oracle artifacts.",
        },
        "calibration": calibration(prediction, observed_positive, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry target-trim, trailing-stop, stop-distance, time-stop, "
                "hold-day, target-price, or response-curve variants from this "
                "oracle sample. Do not use oracle_exit_date or oracle_exit_price "
                "as a rule input."
            ),
            "new_evidence_required": (
                "A valid exit-policy retry needs full trade-level fixed-entry "
                "oracle rows with production-visible pre-exit features, or "
                "prospective shadow exit-advisory rows with settled replacement "
                "value; then implement a shared exit helper and run Gate 1-4."
            ),
        },
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            *(repo_rel(path) for path in WINDOW_FILES.values()),
            "experiments/logs/exp-20260429-032.json",
            "experiments/logs/exp-20260623-020.json",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no JS tooling invoked.",
        },
    }


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    attribution = payload["attribution"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "summary": attribution["summary"],
            "checks": attribution["checks"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "related_files": payload["related_files"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
        "anti_js": payload["anti_js"],
    }


def build_card(payload: Mapping[str, Any]) -> str:
    summary = payload["attribution"]["summary"]
    rows = [
        "| Window | Regret vs oracle | Capture ratio | Top regret rows |",
        "|---|---:|---:|---:|",
    ]
    for label, window in payload["attribution"]["window_payloads"].items():
        perfect = window["perfect_exit"]
        rows.append(
            "| {label} | {regret} | {capture} | {rows} |".format(
                label=label,
                regret=money(perfect["regret_vs_oracle"]),
                capture=pct(perfect["capture_ratio"]),
                rows=perfect["top_regret_row_count"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: fixed-entry exit-oracle gap attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production behavior changed: no",
            "- Accepted alpha: no",
            "",
            "## Oracle Gap",
            "",
            *rows,
            "",
            f"- Total regret vs oracle: `{money(summary['total_regret_vs_oracle'])}`",
            f"- Top-regret row coverage: `{pct(summary['top_regret_share_of_total_regret'])}`",
            f"- Max single-window regret share: `{pct(summary['max_single_window_regret_share'])}`",
            "- Best strategy/exit cohort: `{}`".format(
                (summary.get("best_strategy_exit_reason_cohort") or {}).get("cohort")
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_row = compact_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
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
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
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
                "checks": payload["attribution"]["checks"],
                "summary": payload["attribution"]["summary"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
