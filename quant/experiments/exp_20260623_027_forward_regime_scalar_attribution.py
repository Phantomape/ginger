"""exp-20260623-027: forward regime exposure-scalar attribution.

Observed-only alpha attribution. This runner tests whether the entry-time
regime_chop exposure scalar that was attached to closed forward replacement
rows in exp-20260623-002 already separates replacement value monotonically.

No strategy, helper, ranking, sizing, exit, order, paper ledger, live ledger,
or daily production behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-027"
OWNER = "alpha-explore"
SLUG = "forward_regime_scalar_attribution"
RUNNER = f"quant/experiments/exp_20260623_027_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_027_{SLUG}.json"
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
FORWARD_REPLACEMENT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"

HYPOTHESIS = (
    "Observed-only attribution: closed forward replacement rows tagged by "
    "exp-20260623-002 should show monotonic replacement value improvement as "
    "entry_regime_exposure_scalar rises; otherwise the regime soft-tilt is "
    "not forward-ready."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "regime_router_forward_attribution"
TRIAL_FAMILY = "forward_replacement_entry_regime_exposure_scalar"
TRIAL_VARIANT_ID = "closed_forward_rows_exposure_scalar_tertiles_v1"
CHANGED_VARIABLE = "forward_replacement_entry_regime_exposure_scalar_monotonicity_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260615-025",
    "exp-20260622-017",
    "exp-20260623-002",
    "exp-20260623-004",
]
NEW_EVIDENCE_AXIS = (
    "New evidence is not a retuned regime classifier or frozen-window slice: "
    "exp-20260623-002 added entry-time regime_chop exposure_scalar tags to "
    "closed forward replacement-value rows, enabling a forward-only "
    "monotonicity check before any tilt promotion."
)
CAUSAL_COMPONENTS = [
    "read-only forward rows",
    "entry-time regime_chop exposure scalar",
    "cash/SPY/QQQ replacement-value buckets",
    "no strategy behavior change",
]

CONFIG = {
    "min_rows": 30,
    "min_tagged_rows": 30,
    "min_bucket_rows": 8,
    "min_scalar_range": 0.04,
    "max_single_positive_cash_share": 0.50,
}
BUCKETS = ["low_exposure", "mid_exposure", "high_exposure"]

DEFAULT_PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "forward_rows_too_thin",
        "exposure_scalar_range_too_narrow",
        "no_monotonicity",
        "low_deployment_etf_concentration",
    ],
    "confidence_reason": (
        "Playbook explicitly asks to validate regime_chop exposure_scalar on "
        "entry-regime-tagged forward rows before any sleeve tilt. Prior "
        "frozen-window evidence was sleeve-specific and core-wide tilt failed; "
        "current forward rows are likely thin and concentrated, so success "
        "probability is low."
    ),
    "recorded_at": "2026-06-23T22:04:37+00:00",
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        output = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(output):
        return None
    return output


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranked = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        avg_rank = (start + 1 + end) / 2.0
        for offset in range(start, end):
            ranked[order[offset]] = avg_rank
        start = end
    return ranked


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
    return round(numerator / (den_x * den_y), 6)


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or dict(DEFAULT_PREDICTION)


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
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
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def row_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("decision_id") or ""),
            str(row.get("sleeve_key") or ""),
            str(row.get("ticker") or ""),
            str(row.get("entry_date") or ""),
            str(row.get("exit_date") or ""),
        ]
    )


def load_forward_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows = read_jsonl(FORWARD_REPLACEMENT)
    deduped: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        deduped[row_key(row)] = row

    rows: list[dict[str, Any]] = []
    for row in deduped.values():
        scalar = as_float(row.get("entry_regime_exposure_scalar"))
        cash = as_float(row.get("replacement_value_vs_cash_usd"))
        spy = as_float(row.get("replacement_value_vs_spy_usd"))
        qqq = as_float(row.get("replacement_value_vs_qqq_usd"))
        if scalar is None or cash is None or spy is None or qqq is None:
            continue
        if row.get("entry_regime_status") != "ok":
            continue
        rows.append(
            {
                **row,
                "entry_regime_exposure_scalar": scalar,
                "replacement_value_vs_cash_usd": cash,
                "replacement_value_vs_spy_usd": spy,
                "replacement_value_vs_qqq_usd": qqq,
                "p_choppy_range": as_float(row.get("entry_regime_p_choppy_range")),
                "entry_month": str(row.get("entry_date") or "")[:7],
            }
        )
    rows.sort(
        key=lambda row: (
            row["entry_regime_exposure_scalar"],
            str(row.get("entry_date") or ""),
            str(row.get("sleeve_key") or ""),
            str(row.get("ticker") or ""),
        )
    )
    return rows, {
        "source_artifact": repo_rel(FORWARD_REPLACEMENT),
        "raw_rows": len(raw_rows),
        "deduped_rows": len(deduped),
        "tagged_usable_rows": len(rows),
        "rows_missing_usable_scalar_or_replacement": len(deduped) - len(rows),
        "artifact_not_mutated": True,
    }


def assign_buckets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    output: list[dict[str, Any]] = []
    total = len(rows)
    for index, row in enumerate(rows):
        if index < total / 3:
            bucket = "low_exposure"
        elif index < 2 * total / 3:
            bucket = "mid_exposure"
        else:
            bucket = "high_exposure"
        output.append({**row, "exposure_bucket": bucket})
    return output


def concentration(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    positive_by_ticker: dict[str, float] = defaultdict(float)
    positive_by_sleeve: dict[str, float] = defaultdict(float)
    for row in rows:
        value = as_float(row.get(field))
        if value is not None and value > 0:
            positive_by_ticker[str(row.get("ticker") or "unknown")] += value
            positive_by_sleeve[str(row.get("sleeve_key") or "unknown")] += value
    total = sum(positive_by_ticker.values())
    if total <= 0:
        return {
            "positive_total": 0.0,
            "max_single_ticker_positive_share": None,
            "max_single_sleeve_positive_share": None,
            "top_positive_tickers": [],
            "top_positive_sleeves": [],
        }
    return {
        "positive_total": round(total, 2),
        "max_single_ticker_positive_share": round(
            max(positive_by_ticker.values()) / total, 6
        ),
        "max_single_sleeve_positive_share": round(max(positive_by_sleeve.values()) / total, 6),
        "top_positive_tickers": [
            {
                "ticker": ticker,
                "positive_value": round(value, 2),
                "share": round(value / total, 6),
            }
            for ticker, value in sorted(
                positive_by_ticker.items(), key=lambda item: item[1], reverse=True
            )[:8]
        ],
        "top_positive_sleeves": [
            {
                "sleeve": sleeve,
                "positive_value": round(value, 2),
                "share": round(value / total, 6),
            }
            for sleeve, value in sorted(
                positive_by_sleeve.items(), key=lambda item: item[1], reverse=True
            )[:8]
        ],
    }


def top_counts(rows: list[dict[str, Any]], key: str, limit: int = 8) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or "unknown") for row in rows)
    return [
        {"key": value, "n": count, "row_share": round(count / len(rows), 6) if rows else None}
        for value, count in counts.most_common(limit)
    ]


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "replacement_value_vs_cash_usd",
        "replacement_value_vs_spy_usd",
        "replacement_value_vs_qqq_usd",
    ]
    summary: dict[str, Any] = {
        "n": len(rows),
        "distinct_tickers": len({str(row.get("ticker") or "unknown") for row in rows}),
        "sleeves": top_counts(rows, "sleeve_key"),
        "tickers": top_counts(rows, "ticker"),
        "entry_months": sorted({str(row.get("entry_month") or "unknown") for row in rows}),
        "entry_regimes": top_counts(rows, "entry_regime_label"),
        "scalar_mean": round_or_none(mean([row["entry_regime_exposure_scalar"] for row in rows])),
        "scalar_min": round_or_none(min((row["entry_regime_exposure_scalar"] for row in rows), default=None)),
        "scalar_max": round_or_none(max((row["entry_regime_exposure_scalar"] for row in rows), default=None)),
    }
    for field in fields:
        values = [float(row[field]) for row in rows if as_float(row.get(field)) is not None]
        summary[field] = {
            "sum": round(sum(values), 2) if values else 0.0,
            "mean": round_or_none(mean(values), 4),
            "median": round_or_none(median(values), 4) if values else None,
            "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6)
            if values
            else None,
            "concentration": concentration(rows, field),
        }
    return summary


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for bucket in BUCKETS:
        output[bucket] = summarize_rows([row for row in rows if row["exposure_bucket"] == bucket])
    return output


def month_support(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_month[str(row.get("entry_month") or "unknown")].append(row)
    month_rows = {}
    supportive = 0
    comparable = 0
    for month, month_group in sorted(by_month.items()):
        buckets = bucket_summary(month_group)
        low = buckets["low_exposure"]["replacement_value_vs_cash_usd"]["mean"]
        high = buckets["high_exposure"]["replacement_value_vs_cash_usd"]["mean"]
        if low is not None and high is not None:
            comparable += 1
            if high > low:
                supportive += 1
        month_rows[month] = {
            "n": len(month_group),
            "low_mean_cash": low,
            "high_mean_cash": high,
            "high_beats_low_cash": None if low is None or high is None else high > low,
        }
    return {
        "months": month_rows,
        "comparable_month_count": comparable,
        "high_beats_low_month_count": supportive,
    }


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = assign_buckets(rows)
    scalars = [row["entry_regime_exposure_scalar"] for row in rows]
    cash = [row["replacement_value_vs_cash_usd"] for row in rows]
    spy = [row["replacement_value_vs_spy_usd"] for row in rows]
    qqq = [row["replacement_value_vs_qqq_usd"] for row in rows]
    choppy_pairs = [
        (row["p_choppy_range"], row["replacement_value_vs_cash_usd"])
        for row in rows
        if as_float(row.get("p_choppy_range")) is not None
    ]
    summaries = bucket_summary(rows)
    scalar_range = (max(scalars) - min(scalars)) if scalars else 0.0
    return {
        "all_rows": summarize_rows(rows),
        "bucket_summary": summaries,
        "month_support": month_support(rows),
        "scalar_range": round(scalar_range, 6),
        "spearman_scalar_to_cash": spearman(scalars, cash),
        "spearman_scalar_to_spy": spearman(scalars, spy),
        "spearman_scalar_to_qqq": spearman(scalars, qqq),
        "spearman_p_choppy_to_cash": spearman(
            [item[0] for item in choppy_pairs],
            [item[1] for item in choppy_pairs],
        )
        if choppy_pairs
        else None,
        "sample_rows": [
            {
                "sleeve_key": row.get("sleeve_key"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "entry_regime_label": row.get("entry_regime_label"),
                "entry_regime_exposure_scalar": round_or_none(
                    row.get("entry_regime_exposure_scalar")
                ),
                "exposure_bucket": row.get("exposure_bucket"),
                "replacement_value_vs_cash_usd": round_or_none(
                    row.get("replacement_value_vs_cash_usd"), 2
                ),
                "replacement_value_vs_spy_usd": round_or_none(
                    row.get("replacement_value_vs_spy_usd"), 2
                ),
                "replacement_value_vs_qqq_usd": round_or_none(
                    row.get("replacement_value_vs_qqq_usd"), 2
                ),
            }
            for row in rows[:12]
        ],
    }


def acceptance_checks(analysis: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    all_rows = analysis["all_rows"]
    buckets = analysis["bucket_summary"]
    low = buckets["low_exposure"]
    high = buckets["high_exposure"]
    high_cash = high["replacement_value_vs_cash_usd"]
    high_spy = high["replacement_value_vs_spy_usd"]
    high_qqq = high["replacement_value_vs_qqq_usd"]
    low_cash = low["replacement_value_vs_cash_usd"]
    low_spy = low["replacement_value_vs_spy_usd"]
    low_qqq = low["replacement_value_vs_qqq_usd"]

    checks = {
        "min_rows_passed": all_rows["n"] >= CONFIG["min_rows"],
        "min_bucket_rows_passed": all(
            buckets[bucket]["n"] >= CONFIG["min_bucket_rows"] for bucket in BUCKETS
        ),
        "scalar_range_passed": analysis["scalar_range"] >= CONFIG["min_scalar_range"],
        "spearman_cash_positive": (analysis["spearman_scalar_to_cash"] or 0.0) > 0.0,
        "spearman_spy_positive": (analysis["spearman_scalar_to_spy"] or 0.0) > 0.0,
        "spearman_qqq_positive": (analysis["spearman_scalar_to_qqq"] or 0.0) > 0.0,
        "high_mean_cash_beats_low": (high_cash["mean"] or -10**9) > (low_cash["mean"] or 10**9),
        "high_median_cash_beats_low": (high_cash["median"] or -10**9)
        > (low_cash["median"] or 10**9),
        "high_mean_spy_beats_low": (high_spy["mean"] or -10**9) > (low_spy["mean"] or 10**9),
        "high_mean_qqq_beats_low": (high_qqq["mean"] or -10**9) > (low_qqq["mean"] or 10**9),
        "high_sums_positive": (
            high_cash["sum"] > 0 and high_spy["sum"] > 0 and high_qqq["sum"] > 0
        ),
        "cash_positive_concentration_passed": (
            all_rows["replacement_value_vs_cash_usd"]["concentration"][
                "max_single_ticker_positive_share"
            ]
            is not None
            and all_rows["replacement_value_vs_cash_usd"]["concentration"][
                "max_single_ticker_positive_share"
            ]
            <= CONFIG["max_single_positive_cash_share"]
        ),
        "month_support_passed": analysis["month_support"]["high_beats_low_month_count"] >= 2,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return checks, failed


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    observed_modes = []
    if "min_rows_passed" in failed:
        observed_modes.append("forward_rows_too_thin")
    if "scalar_range_passed" in failed:
        observed_modes.append("exposure_scalar_range_too_narrow")
    if any(reason.startswith("spearman_") for reason in failed) or any(
        "beats_low" in reason for reason in failed
    ):
        observed_modes.append("no_monotonicity")
    if "cash_positive_concentration_passed" in failed:
        observed_modes.append("low_deployment_etf_concentration")
    declared = set(prediction.get("main_failure_modes") or [])
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": int(actual),
        "brier_score": round((probability - actual) ** 2, 6),
        "failed_reasons": failed,
        "failure_modes_observed": observed_modes,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "predicted_failure_mode_hit": bool(declared & set(observed_modes)),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    rows, source_audit = load_forward_rows()
    analysis = analyze(rows)
    checks, failed = acceptance_checks(analysis)
    observed_lead = not failed
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_forward_regime_scalar_lead_not_promoted"
        if observed_lead
        else "rejected_no_forward_regime_scalar_monotonicity"
    )
    why = (
        "The exposure scalar separated current closed forward replacement rows, "
        "but this remains observed-only and no sleeve tilt was promoted."
        if observed_lead
        else "The current entry-regime-tagged forward rows do not show robust "
        "monotonic replacement-value improvement as exposure_scalar rises. "
        "The sample is still a forward attribution surface, not activation "
        "evidence for a regime soft tilt."
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
        "observed_only_lead": observed_lead,
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
        "new_evidence_type": "entry_regime_tagged_forward_replacement_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation was initially blocked as a regime-state "
                    "near-neighbor; novelty override recorded the new evidence "
                    "axis as exp-20260623-002 closed-forward entry-regime tags."
                ),
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: read closed forward rows, "
                "bucket entry_regime_exposure_scalar into tertiles, and test "
                "cash/SPY/QQQ replacement-value monotonicity."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if sample and bucket row counts pass, "
                "scalar range is meaningful, scalar Spearman versus cash/SPY/QQQ "
                "is positive, high-exposure bucket beats low-exposure bucket on "
                "mean/median cash and mean SPY/QQQ replacement value, high bucket "
                "has positive sums, concentration passes, and at least two entry "
                "months support high>low cash value."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_artifact": repo_rel(FORWARD_REPLACEMENT),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
            "bucket_method": "tertiles on entry_regime_exposure_scalar",
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(rows),
            "source_audit": source_audit,
            "fields_checked": [
                "entry_date",
                "exit_date",
                "sleeve_key",
                "ticker",
                "entry_regime_status",
                "entry_regime_exposure_scalar",
                "entry_regime_p_choppy_range",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in rows),
            "target_price_relevance": (
                "Not applicable: no target exit, entry, order, or paper ledger "
                "mutation is scheduled by this observed-only attribution."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": source_audit["deduped_rows"],
            "signals_survived": source_audit["tagged_usable_rows"],
            "survival_rate": round(
                source_audit["tagged_usable_rows"] / source_audit["deduped_rows"], 4
            )
            if source_audit["deduped_rows"]
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "decision": decision,
            "failed_reasons": failed,
            "acceptance_checks": checks,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Forward-only closed paper rows, not canonical fixed-window evidence.",
                "No shared helper, daily adapter, rank, notional, exit, or order rule changed.",
                "Any positive lead would require a separate activation-envelope Gate 1-4.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "analysis": analysis,
            "source_audit": source_audit,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "parity_note": "Read-only attribution over existing forward replacement artifact.",
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing exposure-scalar floor, regime constants, "
                "tertile boundaries, row-count gates, concentration guards, source "
                "rank, notional, hold days, or cooldown on the same closed rows."
            ),
            "new_evidence_required": (
                "Need materially more closed forward replacement rows carrying "
                "entry_regime tags across diversified sleeves and non-risk-on "
                "states before any regime soft-tilt activation test."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_REPLACEMENT),
            repo_rel(BASELINE_RESULT),
            "quant/regime_chop_state.py",
            "experiments/logs/exp-20260615-025.json",
            "experiments/logs/exp-20260622-017.json",
            "experiments/logs/exp-20260623-002.json",
            "experiments/logs/exp-20260623-004.json",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
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
            "all_rows": analysis["all_rows"],
            "bucket_summary": analysis["bucket_summary"],
            "month_support": analysis["month_support"],
            "scalar_range": analysis["scalar_range"],
            "spearman_scalar_to_cash": analysis["spearman_scalar_to_cash"],
            "spearman_scalar_to_spy": analysis["spearman_scalar_to_spy"],
            "spearman_scalar_to_qqq": analysis["spearman_scalar_to_qqq"],
            "spearman_p_choppy_to_cash": analysis["spearman_p_choppy_to_cash"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": payload["anti_js"],
    }


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    buckets = analysis["bucket_summary"]
    rows = [
        "| Bucket | Rows | Mean Cash | Median Cash | Mean vs SPY | Mean vs QQQ | Scalar Mean |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKETS:
        summary = buckets[bucket]
        rows.append(
            "| {bucket} | {n} | {cash_mean} | {cash_median} | {spy_mean} | {qqq_mean} | {scalar} |".format(
                bucket=bucket,
                n=summary["n"],
                cash_mean=money(summary["replacement_value_vs_cash_usd"]["mean"]),
                cash_median=money(summary["replacement_value_vs_cash_usd"]["median"]),
                spy_mean=money(summary["replacement_value_vs_spy_usd"]["mean"]),
                qqq_mean=money(summary["replacement_value_vs_qqq_usd"]["mean"]),
                scalar=summary["scalar_mean"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: forward regime scalar attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Exposure Buckets",
            "",
            *rows,
            "",
            f"- Rows evaluated: `{analysis['all_rows']['n']}`",
            f"- Scalar range: `{analysis['scalar_range']}`",
            f"- Spearman(scalar, cash): `{analysis['spearman_scalar_to_cash']}`",
            f"- Spearman(scalar, SPY replacement): `{analysis['spearman_scalar_to_spy']}`",
            f"- Spearman(scalar, QQQ replacement): `{analysis['spearman_scalar_to_qqq']}`",
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
        "calibration": payload["calibration"],
        "attribution": {
            "all_rows": payload["attribution"]["analysis"]["all_rows"],
            "bucket_summary": payload["attribution"]["analysis"]["bucket_summary"],
            "scalar_range": payload["attribution"]["analysis"]["scalar_range"],
            "spearman_scalar_to_cash": payload["attribution"]["analysis"][
                "spearman_scalar_to_cash"
            ],
            "spearman_scalar_to_spy": payload["attribution"]["analysis"][
                "spearman_scalar_to_spy"
            ],
            "spearman_scalar_to_qqq": payload["attribution"]["analysis"][
                "spearman_scalar_to_qqq"
            ],
        },
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
    analysis = payload["attribution"]["analysis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "rows": analysis["all_rows"]["n"],
                "scalar_range": analysis["scalar_range"],
                "spearman_cash": analysis["spearman_scalar_to_cash"],
                "spearman_spy": analysis["spearman_scalar_to_spy"],
                "spearman_qqq": analysis["spearman_scalar_to_qqq"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
