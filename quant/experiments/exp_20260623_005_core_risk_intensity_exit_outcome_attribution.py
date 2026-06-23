"""exp-20260623-005: risk-intensity x exit-outcome attribution.

Observed-only alpha attribution. This runner tests whether the positive
core-risk-intensity lead from exp-20260622-019/020 survives after conditioning
on production-visible exit outcome and the fixed-entry oracle-capture buckets
from exp-20260623-003.

It changes no entry, ranking, sizing, exit, live, or paper order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-005"
SLUG = "core_risk_intensity_exit_outcome_attribution"
RUNNER = f"quant/experiments/exp_20260623_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_005_{SLUG}.json"
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
WINDOW_FILES = {
    "late_strong": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    "mid_weak": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    "old_thin": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
}
ORACLE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-003"
    / "exp_20260623_003_fixed_entry_exit_oracle_regret_cluster.json"
)

HYPOTHESIS = (
    "Observed-only risk_allocation attribution: accepted core risk-intensity "
    "should remain predictive within production-visible exit outcome and "
    "oracle-capture buckets, otherwise the exp-20260622-019/020 lead is mostly "
    "target-winner selection rather than deployable sizing alpha."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "risk_allocation_attribution"
TRIAL_FAMILY = "core_risk_intensity_exit_outcome_attribution"
TRIAL_VARIANT_ID = "canonical_windows_exit_bucket_interaction_v1"
CHANGED_VARIABLE = "core_risk_intensity_exit_outcome_attribution_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-019",
    "exp-20260622-020",
    "exp-20260623-003",
]
NEW_EVIDENCE_TYPE = "risk_intensity_exit_outcome_interaction_attribution"
NEW_EVIDENCE_AXIS = (
    "New gate shape: cross-axis attribution of the positive risk-intensity "
    "lead against production-visible exit_reason and fixed-entry oracle-capture "
    "buckets; no scalar, threshold, or exit retune."
)
CAUSAL_COMPONENTS = [
    "canonical closed core trades",
    "risk-intensity x exit-outcome attribution",
    "no strategy change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-005/exp_20260623_005_core_risk_intensity_exit_outcome_attribution.json",
    "experiments/cards/exp-20260623-005.md",
    "experiments/manifests/exp-20260623-005.json",
    "experiments/tickets/exp-20260623-005.json",
    "experiments/logs/exp-20260623-005.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
ACCEPTANCE_RULE = {
    "min_trade_rows": 55,
    "min_oracle_join_rows": 55,
    "min_target_rows": 20,
    "min_stop_rows": 15,
    "min_exit_groups_with_nonnegative_spearman": 2,
    "max_stop_high_bucket_loss_vs_low_bucket": 0.0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    out = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        avg_rank = (cursor + 1 + end) / 2.0
        for rank_index in range(cursor, end):
            out[order[rank_index]] = avg_rank
        cursor = end
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 4:
        return None
    rx = ranks(xs)
    ry = ranks(ys)
    mean_x = sum(rx) / len(rx)
    mean_y = sum(ry) / len(ry)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(rx, ry))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in rx))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ry))
    if den_x == 0 or den_y == 0:
        return None
    return round(numerator / (den_x * den_y), 4)


def residualize(
    rows: list[dict[str, Any]],
    values: list[float],
    dimensions: list[str],
    *,
    iterations: int = 80,
    min_group_size: int = 2,
) -> list[float]:
    if not values:
        return []
    global_mean = sum(values) / len(values)
    residuals = [value - global_mean for value in values]
    dimension_groups: list[list[list[int]]] = []
    for dimension in dimensions:
        buckets: dict[str, list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            buckets[str(row.get(dimension) or "unknown")].append(index)
        dimension_groups.append(
            [indices for indices in buckets.values() if len(indices) >= min_group_size]
        )

    for _ in range(iterations):
        max_adjustment = 0.0
        for groups in dimension_groups:
            for indices in groups:
                mean_residual = sum(residuals[index] for index in indices) / len(indices)
                if mean_residual:
                    for index in indices:
                        residuals[index] -= mean_residual
                    max_adjustment = max(max_adjustment, abs(mean_residual))
        if max_adjustment < 1e-10:
            break
    return residuals


def median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(median(values)), 4)


def load_ticket_prediction() -> dict[str, Any]:
    fallback = {
        "success_probability": 0.26,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "target_winner_explains_relation",
            "stop_bucket_negative_convexity",
            "thin_exit_subgroups",
            "old_thin_regret_concentration",
            "endogenous_sizing_stack",
        ],
        "confidence_reason": (
            "Risk intensity survived residual controls in exp-20260622-020, "
            "but exit oracle attribution in exp-20260623-003 showed target rows "
            "already capture most oracle PnL and stop regret is old_thin-heavy."
        ),
        "recorded_at": "2026-06-23T04:05:34+00:00",
    }
    if not TICKET_JSON.exists():
        return fallback
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction")
    return prediction if isinstance(prediction, dict) and prediction else fallback


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
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            float(window.get("max_drawdown_pct") or 0.0) for window in windows
        )
        if windows
        else None,
        "windows": windows,
    }


def oracle_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("window") or ""),
        str(row.get("ticker") or "").upper(),
        str(row.get("entry_date") or "")[:10],
        str(row.get("actual_exit_date") or row.get("exit_date") or "")[:10],
    )


def load_oracle_rows() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    if not ORACLE_ARTIFACT.exists():
        return {}
    payload = read_json(ORACLE_ARTIFACT)
    rows = payload.get("attribution", {}).get("sample_rows") or []
    return {oracle_key(row): row for row in rows}


def load_trade_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    oracle_by_key = load_oracle_rows()
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    field_presence = {
        "entry_date": 0,
        "target_price": 0,
        "base_risk_pct": 0,
        "actual_risk_pct": 0,
        "pnl": 0,
        "exit_reason": 0,
    }
    total_trades = 0
    oracle_joined = 0
    for window, path in WINDOW_FILES.items():
        data = read_json(path)
        for index, trade in enumerate(data.get("trades") or []):
            total_trades += 1
            for field in field_presence:
                if trade.get(field) is not None:
                    field_presence[field] += 1
            base_risk = as_float(trade.get("base_risk_pct"))
            actual_risk = as_float(trade.get("actual_risk_pct"))
            pnl = as_float(trade.get("pnl"))
            if base_risk is None or base_risk <= 0 or actual_risk is None or actual_risk <= 0:
                skipped.append({"window": window, "index": index, "reason": "bad_risk_fields"})
                continue
            if pnl is None:
                skipped.append({"window": window, "index": index, "reason": "missing_pnl"})
                continue
            key = (
                window,
                str(trade.get("ticker") or "").upper(),
                str(trade.get("entry_date") or "")[:10],
                str(trade.get("exit_date") or "")[:10],
            )
            oracle = oracle_by_key.get(key)
            if oracle is not None:
                oracle_joined += 1
            row = {
                "window": window,
                "trade_key": trade.get("trade_key") or f"{window}:{index}",
                "ticker": trade.get("ticker") or "unknown",
                "sector": trade.get("sector") or "unknown",
                "strategy": trade.get("strategy") or "unknown",
                "entry_date": str(trade.get("entry_date") or "")[:10],
                "exit_date": str(trade.get("exit_date") or "")[:10],
                "exit_reason": trade.get("exit_reason") or "unknown",
                "pnl": pnl,
                "base_risk_pct": base_risk,
                "actual_risk_pct": actual_risk,
                "risk_intensity": actual_risk / base_risk,
                "oracle_joined": oracle is not None,
                "oracle_capture_ratio": as_float(oracle.get("capture_ratio")) if oracle else None,
                "oracle_regret": as_float(oracle.get("regret_vs_oracle")) if oracle else None,
                "oracle_pnl": as_float(oracle.get("oracle_pnl")) if oracle else None,
                "actual_outcome_bucket": (
                    oracle.get("actual_outcome_bucket") if oracle else "oracle_missing"
                ),
                "oracle_timing_bucket": (
                    oracle.get("oracle_timing_bucket") if oracle else "oracle_missing"
                ),
            }
            rows.append(row)
    if field_presence["entry_date"] != total_trades:
        raise ValueError("entry_date missing from one or more closed trade rows")
    return rows, {
        "total_trades": total_trades,
        "usable_trades": len(rows),
        "oracle_rows_available": len(oracle_by_key),
        "oracle_rows_joined": oracle_joined,
        "skipped_trades": skipped,
        "field_presence": field_presence,
    }


def assign_tertiles(rows: list[dict[str, Any]], field: str, output_field: str) -> None:
    ordered = sorted(
        range(len(rows)),
        key=lambda index: (
            rows[index][field],
            rows[index].get("entry_date") or "",
            rows[index].get("ticker") or "",
            rows[index].get("trade_key") or "",
        ),
    )
    n = len(ordered)
    for rank, row_index in enumerate(ordered):
        if rank < n / 3:
            bucket = "low"
        elif rank < (2 * n) / 3:
            bucket = "mid"
        else:
            bucket = "high"
        rows[row_index][output_field] = bucket


def summarize_group(rows: list[dict[str, Any]], *, residual: bool = False) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "total_pnl": 0.0,
            "mean_pnl": None,
            "median_pnl": None,
            "win_rate": None,
            "mean_risk_intensity": None,
            "spearman_risk_intensity_pnl": None,
        }
    pnls = [float(row["pnl"]) for row in rows]
    risks = [float(row["risk_intensity"]) for row in rows]
    out = {
        "n": len(rows),
        "total_pnl": round(sum(pnls), 2),
        "mean_pnl": round(sum(pnls) / len(pnls), 2),
        "median_pnl": round(float(median(pnls)), 2),
        "win_rate": round(sum(1 for pnl in pnls if pnl > 0) / len(rows), 4),
        "mean_risk_intensity": round(sum(risks) / len(risks), 4),
        "median_risk_intensity": round(float(median(risks)), 4),
        "spearman_risk_intensity_pnl": spearman(risks, pnls),
        "windows_present": sorted({str(row["window"]) for row in rows}),
    }
    if residual:
        residual_pnls = [float(row["exit_residual_pnl"]) for row in rows]
        residual_risks = [float(row["exit_residual_risk_intensity"]) for row in rows]
        out.update(
            {
                "mean_exit_residual_pnl": round(sum(residual_pnls) / len(residual_pnls), 4),
                "median_exit_residual_pnl": median_or_none(residual_pnls),
                "mean_exit_residual_risk_intensity": round(
                    sum(residual_risks) / len(residual_risks),
                    6,
                ),
                "spearman_exit_residual_risk_pnl": spearman(residual_risks, residual_pnls),
            }
        )
    return out


def bucket_summary(rows: list[dict[str, Any]], bucket_field: str, *, residual: bool) -> dict[str, Any]:
    return {
        bucket: summarize_group(
            [row for row in rows if row.get(bucket_field) == bucket],
            residual=residual,
        )
        for bucket in ("low", "mid", "high")
    }


def group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field) or "unknown")].append(row)
    return {
        key: {
            **summarize_group(group_rows),
            "risk_bucket_summary": bucket_summary(group_rows, "risk_bucket", residual=False)
            if len(group_rows) >= 9
            else {},
        }
        for key, group_rows in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    }


def add_exit_outcome_residuals(rows: list[dict[str, Any]]) -> None:
    dimensions = [
        "window",
        "exit_reason",
        "actual_outcome_bucket",
        "oracle_timing_bucket",
    ]
    risk_residuals = residualize(rows, [row["risk_intensity"] for row in rows], dimensions)
    pnl_residuals = residualize(rows, [row["pnl"] for row in rows], dimensions)
    for row, risk_value, pnl_value in zip(rows, risk_residuals, pnl_residuals):
        row["exit_residual_risk_intensity"] = risk_value
        row["exit_residual_pnl"] = pnl_value
    assign_tertiles(rows, "exit_residual_risk_intensity", "exit_residual_risk_bucket")


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assign_tertiles(rows, "risk_intensity", "risk_bucket")
    add_exit_outcome_residuals(rows)
    target_rows = [row for row in rows if row["exit_reason"] == "target"]
    stop_rows = [row for row in rows if row["exit_reason"] == "stop"]
    residual_spearman = spearman(
        [row["exit_residual_risk_intensity"] for row in rows],
        [row["exit_residual_pnl"] for row in rows],
    )
    exit_group_nonnegative = [
        key
        for key, summary in group_summary(rows, "exit_reason").items()
        if summary["n"] >= 8
        and summary["spearman_risk_intensity_pnl"] is not None
        and summary["spearman_risk_intensity_pnl"] >= 0
    ]
    stop_buckets = bucket_summary(stop_rows, "risk_bucket", residual=False)
    high_stop_mean = stop_buckets.get("high", {}).get("mean_pnl")
    low_stop_mean = stop_buckets.get("low", {}).get("mean_pnl")
    stop_high_loss_vs_low = (
        round(float(high_stop_mean) - float(low_stop_mean), 4)
        if high_stop_mean is not None and low_stop_mean is not None
        else None
    )
    residual_buckets = bucket_summary(rows, "exit_residual_risk_bucket", residual=True)
    high_residual = residual_buckets["high"]
    low_residual = residual_buckets["low"]
    checks = {
        "acceptance_rule": ACCEPTANCE_RULE,
        "trade_rows": len(rows),
        "oracle_join_rows": sum(1 for row in rows if row["oracle_joined"]),
        "target_rows": len(target_rows),
        "stop_rows": len(stop_rows),
        "exit_groups_with_nonnegative_spearman": exit_group_nonnegative,
        "exit_outcome_residual_spearman": residual_spearman,
        "residual_high_mean_pnl_beats_low": (
            high_residual["mean_exit_residual_pnl"] is not None
            and low_residual["mean_exit_residual_pnl"] is not None
            and high_residual["mean_exit_residual_pnl"] > low_residual["mean_exit_residual_pnl"]
        ),
        "residual_high_median_pnl_beats_low": (
            high_residual["median_exit_residual_pnl"] is not None
            and low_residual["median_exit_residual_pnl"] is not None
            and high_residual["median_exit_residual_pnl"]
            > low_residual["median_exit_residual_pnl"]
        ),
        "stop_high_bucket_mean_minus_low_bucket_mean": stop_high_loss_vs_low,
    }
    failed = []
    if checks["trade_rows"] < ACCEPTANCE_RULE["min_trade_rows"]:
        failed.append("too_few_trade_rows")
    if checks["oracle_join_rows"] < ACCEPTANCE_RULE["min_oracle_join_rows"]:
        failed.append("too_few_oracle_join_rows")
    if checks["target_rows"] < ACCEPTANCE_RULE["min_target_rows"]:
        failed.append("too_few_target_rows")
    if checks["stop_rows"] < ACCEPTANCE_RULE["min_stop_rows"]:
        failed.append("too_few_stop_rows")
    if residual_spearman is None or residual_spearman <= 0:
        failed.append("exit_outcome_residual_spearman_not_positive")
    if not checks["residual_high_mean_pnl_beats_low"]:
        failed.append("residual_high_mean_not_above_low")
    if not checks["residual_high_median_pnl_beats_low"]:
        failed.append("residual_high_median_not_above_low")
    if (
        len(exit_group_nonnegative)
        < ACCEPTANCE_RULE["min_exit_groups_with_nonnegative_spearman"]
    ):
        failed.append("risk_intensity_positive_only_in_too_few_exit_groups")
    if stop_high_loss_vs_low is not None and stop_high_loss_vs_low < ACCEPTANCE_RULE["max_stop_high_bucket_loss_vs_low_bucket"]:
        failed.append("stop_high_risk_bucket_more_negative_than_low")

    return {
        "overall": summarize_group(rows),
        "raw_risk_bucket_summary": bucket_summary(rows, "risk_bucket", residual=False),
        "exit_outcome_residual_bucket_summary": residual_buckets,
        "by_exit_reason": group_summary(rows, "exit_reason"),
        "by_actual_outcome_bucket": group_summary(rows, "actual_outcome_bucket"),
        "by_window": group_summary(rows, "window"),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "observed_only_lead": not failed,
        "sample_rows": [
            {
                key: row.get(key)
                for key in (
                    "window",
                    "ticker",
                    "entry_date",
                    "exit_reason",
                    "pnl",
                    "risk_intensity",
                    "risk_bucket",
                    "actual_outcome_bucket",
                    "oracle_timing_bucket",
                    "oracle_capture_ratio",
                    "exit_residual_risk_bucket",
                    "exit_residual_pnl",
                )
            }
            for row in rows[:200]
        ],
    }


def calibration(prediction: dict[str, Any], observed_only_lead: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if observed_only_lead else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    mode_map = {
        "target_winner_explains_relation": {
            "exit_outcome_residual_spearman_not_positive",
            "residual_high_mean_not_above_low",
            "residual_high_median_not_above_low",
        },
        "stop_bucket_negative_convexity": {"stop_high_risk_bucket_more_negative_than_low"},
        "thin_exit_subgroups": {"too_few_target_rows", "too_few_stop_rows"},
        "old_thin_regret_concentration": set(),
        "endogenous_sizing_stack": {"risk_intensity_positive_only_in_too_few_exit_groups"},
    }
    hit_modes = [
        mode for mode in predicted_modes if mode_map.get(mode, set()).intersection(failed)
    ]
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(observed_only_lead),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "failed_reasons": failed,
        "predicted_failure_modes_hit": hit_modes,
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    rows, field_checks = load_trade_rows()
    analysis = analyze(rows)
    observed_only_lead = bool(analysis["observed_only_lead"])
    failed = list(analysis["failed_reasons"])
    status = "observed_only_positive_lead" if observed_only_lead else "observed_only_rejected"
    decision = (
        "observed_only_core_risk_intensity_exit_outcome_lead_not_promoted"
        if observed_only_lead
        else "rejected_core_risk_intensity_exit_outcome_not_deployable"
    )
    why = (
        "Risk intensity retained positive residual association after demeaning "
        "by window, exit reason, oracle outcome bucket, and oracle timing. This "
        "would still be only a lead because no policy was changed."
        if observed_only_lead
        else "The risk-intensity lead did not survive the exit-outcome interaction screen strongly enough: it is not a deployable sizing rule from the frozen windows, and stop-loss rows expose negative convexity risk."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
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
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted this as no strong near-neighbor.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": (
                    "This is not a risk scalar, top-up, cap, rank, entry, or exit "
                    "retry. It cross-checks the positive risk-intensity lead "
                    "against the rejected exit-oracle regret surface."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: canonical core closed "
                "trades plus risk-intensity x exit-outcome/oracle-capture "
                "interaction analysis."
            ),
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "window_files": {label: repo_rel(path) for label, path in WINDOW_FILES.items()},
            "oracle_artifact": repo_rel(ORACLE_ARTIFACT),
            "risk_intensity_formula": "actual_risk_pct / base_risk_pct",
            "residual_dimensions": [
                "window",
                "exit_reason",
                "actual_outcome_bucket",
                "oracle_timing_bucket",
            ],
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": True,
            "fields_checked": [
                "entry_date",
                "target_price",
                "base_risk_pct",
                "actual_risk_pct",
                "pnl",
                "exit_reason",
                "oracle_capture_ratio",
                "actual_outcome_bucket",
                "oracle_timing_bucket",
            ],
            "entry_date_present": field_checks["field_presence"]["entry_date"]
            == field_checks["total_trades"],
            "target_price_checked": True,
            "target_price_present_count": field_checks["field_presence"]["target_price"],
            "target_price_relevance": (
                "Target price is checked for AGENTS.md Gate 2 but not consumed; "
                "this attribution uses realized exit_reason and oracle fields "
                "without scheduling any target order."
            ),
            "field_presence": field_checks["field_presence"],
            "total_trades": field_checks["total_trades"],
            "usable_trades": field_checks["usable_trades"],
            "oracle_rows_available": field_checks["oracle_rows_available"],
            "oracle_rows_joined": field_checks["oracle_rows_joined"],
            "skipped_trades": field_checks["skipped_trades"],
        },
        "gate3": {
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "observed_rows_survival_rate": 1.0,
            "note": "No executable filter was added; closed trades are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_only_lead,
            "failed_reasons": failed,
            "acceptance_checks": analysis["acceptance_checks"],
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "No trading rule was changed.",
                "Exit/oracle buckets are diagnostic attribution, not live inputs.",
                "Promotion would require forward rows from the existing risk-intensity ledger.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "n_rows": len(rows),
            "analysis": analysis,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "uses_future_oracle": True,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_only_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not convert exp-20260622-019/020/005 into historical "
                "risk scalar, top-up, cap, rank, target-trim, stop-loosening, "
                "or exit-retune sweeps on the same windows. The valid next "
                "evidence is closed forward rows from the existing risk-intensity "
                "ledger, not a frozen-window parameter change."
            ),
            "new_evidence_required": (
                "Closed forward observations with selected/sliced status, "
                "pre-execution risk-intensity rank, realized PnL, exit outcome, "
                "and replacement value before any sizing/ranking promotion."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            *[repo_rel(path) for path in WINDOW_FILES.values()],
            repo_rel(ORACLE_ARTIFACT),
            "experiments/logs/exp-20260622-019.json",
            "experiments/logs/exp-20260622-020.json",
            "experiments/logs/exp-20260623-003.json",
        ],
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        **{key: payload[key] for key in (
            "experiment_id",
            "timestamp",
            "status",
            "lane",
            "owner",
            "decision",
            "accepted",
            "accepted_alpha",
            "observed_only_lead",
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
            "pre_run_questions",
            "parameters",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "production_impact",
            "calibration",
            "post_run_reflection",
            "related_files",
            "anti_js",
        )},
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "overall": analysis["overall"],
            "raw_risk_bucket_summary": analysis["raw_risk_bucket_summary"],
            "exit_outcome_residual_bucket_summary": analysis[
                "exit_outcome_residual_bucket_summary"
            ],
            "by_exit_reason": analysis["by_exit_reason"],
            "acceptance_checks": analysis["acceptance_checks"],
        },
    }


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    raw = analysis["raw_risk_bucket_summary"]
    residual = analysis["exit_outcome_residual_bucket_summary"]
    rows = [
        "| Bucket | Trades | Raw Mean PnL | Raw Median PnL | Residual Mean PnL | Residual Median PnL |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket in ("low", "mid", "high"):
        raw_bucket = raw[bucket]
        residual_bucket = residual[bucket]
        rows.append(
            "| {bucket} | {n} | ${raw_mean:,.2f} | ${raw_median:,.2f} | {res_mean:,.4f} | {res_median:,.4f} |".format(
                bucket=bucket,
                n=raw_bucket["n"],
                raw_mean=raw_bucket["mean_pnl"],
                raw_median=raw_bucket["median_pnl"],
                res_mean=residual_bucket["mean_exit_residual_pnl"],
                res_median=residual_bucket["median_exit_residual_pnl"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: risk-intensity x exit outcome attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Result",
            "",
            *rows,
            "",
            "- Residual Spearman: `{}`".format(
                analysis["acceptance_checks"]["exit_outcome_residual_spearman"]
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


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
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
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
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
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    checks = payload["gate4"]["acceptance_checks"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "trade_rows": checks["trade_rows"],
                "oracle_join_rows": checks["oracle_join_rows"],
                "exit_outcome_residual_spearman": checks[
                    "exit_outcome_residual_spearman"
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
