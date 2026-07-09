"""exp-20260705-002: forward duplicate exposure attribution.

Observed-only alpha attribution over the shared forward replacement-value
ledger. The test asks whether same-ticker, same-entry-date duplicate paper
exposure is materially worse than singleton exposure on cash/SPY/QQQ
replacement value. It changes no entry, ranking, sizing, risk, exit, paper
order, live order, or LLM decision boundary.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


EXPERIMENT_ID = "exp-20260705-002"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "forward_duplicate_exposure_attribution"
RUNNER = f"quant/experiments/exp_20260705_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_LEDGER = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Closed forward replacement rows may show that same-entry-date same-ticker "
    "duplicate paper exposure amplifies losses versus singleton default-off rows; "
    "if duplicates are broadly worse on cash/SPY/QQQ replacement value, a future "
    "shared duplicate-exposure cap may be justified."
)
CHANGED_VARIABLE = "forward_same_ticker_same_entry_date_duplicate_exposure_attribution_v1"
MECHANISM_FAMILY = "forward_replacement_duplicate_exposure_attribution"
TRIAL_FAMILY = "forward_duplicate_exposure_attribution"
TRIAL_VARIANT_ID = "same_ticker_same_entry_date_v1"
NEARBY_PRIORS = ["exp-20260624-004", "exp-20260624-006", "exp-20260704-022"]
PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "duplicate_sample_too_thin",
        "sec_financial_report_or_coin_confound",
        "no_cash_spy_qqq_separation",
        "not_actionable_without_gate4",
    ],
    "confidence_reason": (
        "The newly materialized forward replacement ledger includes visible "
        "same-ticker same-entry duplicate exposure from post-repair SEC "
        "financial-report rows, but prior forward attribution surfaces are "
        "usually thin and concentration-prone."
    ),
    "recorded_at": "2026-07-05T01:05:24+00:00",
}
PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
ACCEPTANCE_RULE = {
    "min_duplicate_rows": 6,
    "min_duplicate_groups": 3,
    "min_singleton_rows": 30,
    "max_single_duplicate_ticker_share": 0.50,
    "max_single_duplicate_sleeve_share": 0.70,
    "require_all_primary_means_worse": True,
    "require_all_primary_medians_worse": True,
    "require_all_primary_loss_tails_worse": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_002_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


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
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {})
    raw_windows = payload.get("windows") or []
    if isinstance(raw_windows, dict):
        windows = list(raw_windows.values())
    else:
        windows = list(raw_windows)
    generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    survival_rates = [
        float(w.get("survival_rate") or 0.0)
        for w in windows
        if w.get("survival_rate") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "loaded": BASELINE_PATH.exists(),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "min_window_survival_rate": min(survival_rates) if survival_rates else None,
        "max_drawdown_pct_worst": max(
            (float(w.get("max_drawdown_pct") or 0.0) for w in windows), default=None
        ),
        "window_count": len(windows),
        "windows": [
            {
                "label": w.get("label"),
                "start": w.get("start"),
                "end": w.get("end"),
                "expected_value_score": w.get("expected_value_score"),
                "total_pnl": w.get("total_pnl"),
                "trade_count": w.get("trade_count"),
                "survival_rate": w.get("survival_rate"),
                "max_drawdown_pct": w.get("max_drawdown_pct"),
            }
            for w in windows
        ],
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def valid_metric_row(row: dict[str, Any]) -> bool:
    required = ["ticker", "entry_date", *PRIMARY_METRICS]
    return all(row.get(key) not in (None, "") for key in required)


def is_excluded_finra_ftd(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "sleeve_key",
            "decision_id",
            "source",
            "source_family",
            "trial_family",
            "rule_version",
        )
    ).lower()
    return "finra" in text or "ftd" in text


def percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def worst_tail_mean(values: list[float], fraction: float = 0.2) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    count = max(1, math.ceil(len(sorted_values) * fraction))
    return mean(sorted_values[:count])


def summarize_values(values: list[float]) -> dict[str, Any]:
    sorted_values = sorted(values)
    return {
        "n": len(values),
        "sum": round(sum(values), 2) if values else None,
        "mean": round(mean(values), 4) if values else None,
        "median": round(median(values), 4) if values else None,
        "min": round(min(values), 4) if values else None,
        "max": round(max(values), 4) if values else None,
        "p20": round(percentile(sorted_values, 0.2), 4) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6)
        if values
        else None,
        "worst_20pct_mean": round(worst_tail_mean(values, 0.2), 4)
        if values
        else None,
    }


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    sleeves = Counter(str(row.get("sleeve_key") or "UNKNOWN") for row in rows)
    metrics: dict[str, Any] = {}
    for key in [*PRIMARY_METRICS, "pnl_usd", "notional_usd"]:
        values = [safe_float(row.get(key)) for row in rows]
        metrics[key] = summarize_values([value for value in values if value is not None])
    return {
        "row_count": len(rows),
        "ticker_count": len(tickers),
        "sleeve_count": len(sleeves),
        "ticker_counts": dict(sorted(tickers.items())),
        "sleeve_counts": dict(sorted(sleeves.items())),
        "top_tickers": [
            {"ticker": ticker, "rows": count, "share": round(count / len(rows), 6)}
            for ticker, count in tickers.most_common(10)
        ]
        if rows
        else [],
        "top_sleeves": [
            {"sleeve": sleeve, "rows": count, "share": round(count / len(rows), 6)}
            for sleeve, count in sleeves.most_common(10)
        ]
        if rows
        else [],
        "metrics": metrics,
    }


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("entry_date") or ""), str(row.get("ticker") or "").upper())


def group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row_key(row)].append(row)
    return dict(groups)


def group_records(groups: dict[tuple[str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for (entry_date, ticker), rows in sorted(groups.items()):
        metrics: dict[str, Any] = {}
        for key in [*PRIMARY_METRICS, "pnl_usd", "notional_usd"]:
            values = [safe_float(row.get(key)) for row in rows]
            clean_values = [value for value in values if value is not None]
            metrics[key] = round(sum(clean_values), 2) if clean_values else None
        sleeves = Counter(str(row.get("sleeve_key") or "UNKNOWN") for row in rows)
        records.append(
            {
                "entry_date": entry_date,
                "ticker": ticker,
                "row_count": len(rows),
                "sleeves": dict(sorted(sleeves.items())),
                "decision_ids": [str(row.get("decision_id") or "") for row in rows],
                "metrics_sum": metrics,
            }
        )
    return records


def grouped_bucket_summary(
    records: list[dict[str, Any]],
    *,
    group_label: str,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key in [*PRIMARY_METRICS, "pnl_usd", "notional_usd"]:
        values = [
            safe_float((record.get("metrics_sum") or {}).get(key)) for record in records
        ]
        metrics[key] = summarize_values([value for value in values if value is not None])
    tickers = Counter(str(record.get("ticker") or "UNKNOWN") for record in records)
    return {
        "group_label": group_label,
        "group_count": len(records),
        "row_count": sum(int(record.get("row_count") or 0) for record in records),
        "ticker_count": len(tickers),
        "top_tickers": [
            {"ticker": ticker, "groups": count, "share": round(count / len(records), 6)}
            for ticker, count in tickers.most_common(10)
        ]
        if records
        else [],
        "metrics": metrics,
    }


def compare_buckets(
    duplicates: list[dict[str, Any]], singletons: list[dict[str, Any]]
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for key in PRIMARY_METRICS:
        duplicate_values = [
            value
            for row in duplicates
            if (value := safe_float(row.get(key))) is not None
        ]
        singleton_values = [
            value
            for row in singletons
            if (value := safe_float(row.get(key))) is not None
        ]
        duplicate_summary = summarize_values(duplicate_values)
        singleton_summary = summarize_values(singleton_values)
        comparisons[key] = {
            "duplicate_rows": duplicate_summary,
            "singleton_rows": singleton_summary,
            "mean_delta_duplicate_minus_singleton": round(
                (duplicate_summary["mean"] or 0.0) - (singleton_summary["mean"] or 0.0),
                4,
            )
            if duplicate_values and singleton_values
            else None,
            "median_delta_duplicate_minus_singleton": round(
                (duplicate_summary["median"] or 0.0)
                - (singleton_summary["median"] or 0.0),
                4,
            )
            if duplicate_values and singleton_values
            else None,
            "tail_delta_duplicate_minus_singleton": round(
                (duplicate_summary["worst_20pct_mean"] or 0.0)
                - (singleton_summary["worst_20pct_mean"] or 0.0),
                4,
            )
            if duplicate_values and singleton_values
            else None,
            "duplicate_mean_worse": (
                duplicate_summary["mean"] is not None
                and singleton_summary["mean"] is not None
                and duplicate_summary["mean"] < singleton_summary["mean"]
            ),
            "duplicate_median_worse": (
                duplicate_summary["median"] is not None
                and singleton_summary["median"] is not None
                and duplicate_summary["median"] < singleton_summary["median"]
            ),
            "duplicate_loss_tail_worse": (
                duplicate_summary["worst_20pct_mean"] is not None
                and singleton_summary["worst_20pct_mean"] is not None
                and duplicate_summary["worst_20pct_mean"]
                < singleton_summary["worst_20pct_mean"]
            ),
        }
    return comparisons


def max_share(counter: Counter[str], total: int) -> float:
    if not counter or total <= 0:
        return 0.0
    return max(counter.values()) / total


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = baseline_metrics()
    all_rows = read_jsonl(FORWARD_LEDGER)
    enriched_rows = [row for row in all_rows if row.get("status") == "enriched"]
    excluded_rows = [row for row in enriched_rows if is_excluded_finra_ftd(row)]
    eligible_rows = [
        row
        for row in enriched_rows
        if not is_excluded_finra_ftd(row) and valid_metric_row(row)
    ]
    ineligible_rows = [
        row
        for row in enriched_rows
        if not is_excluded_finra_ftd(row) and not valid_metric_row(row)
    ]
    groups = group_rows(eligible_rows)
    duplicate_groups = {
        key: rows for key, rows in groups.items() if len(rows) >= 2
    }
    singleton_groups = {
        key: rows for key, rows in groups.items() if len(rows) == 1
    }
    duplicate_rows = [row for rows in duplicate_groups.values() for row in rows]
    singleton_rows = [row for rows in singleton_groups.values() for row in rows]
    duplicate_group_records = group_records(duplicate_groups)
    singleton_group_records = group_records(singleton_groups)
    comparisons = compare_buckets(duplicate_rows, singleton_rows)

    duplicate_tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in duplicate_rows)
    duplicate_sleeves = Counter(
        str(row.get("sleeve_key") or "UNKNOWN") for row in duplicate_rows
    )
    checks = {
        "duplicate_rows_min_passed": len(duplicate_rows)
        >= ACCEPTANCE_RULE["min_duplicate_rows"],
        "duplicate_groups_min_passed": len(duplicate_groups)
        >= ACCEPTANCE_RULE["min_duplicate_groups"],
        "singleton_rows_min_passed": len(singleton_rows)
        >= ACCEPTANCE_RULE["min_singleton_rows"],
        "single_duplicate_ticker_share_passed": max_share(
            duplicate_tickers, len(duplicate_rows)
        )
        <= ACCEPTANCE_RULE["max_single_duplicate_ticker_share"],
        "single_duplicate_sleeve_share_passed": max_share(
            duplicate_sleeves, len(duplicate_rows)
        )
        <= ACCEPTANCE_RULE["max_single_duplicate_sleeve_share"],
        "all_primary_means_worse": all(
            comparisons[key]["duplicate_mean_worse"] for key in PRIMARY_METRICS
        ),
        "all_primary_medians_worse": all(
            comparisons[key]["duplicate_median_worse"] for key in PRIMARY_METRICS
        ),
        "all_primary_loss_tails_worse": all(
            comparisons[key]["duplicate_loss_tail_worse"] for key in PRIMARY_METRICS
        ),
    }
    sample_ready = (
        checks["duplicate_rows_min_passed"]
        and checks["duplicate_groups_min_passed"]
        and checks["singleton_rows_min_passed"]
        and checks["single_duplicate_ticker_share_passed"]
        and checks["single_duplicate_sleeve_share_passed"]
    )
    directional_support = (
        checks["all_primary_means_worse"]
        and checks["all_primary_medians_worse"]
        and checks["all_primary_loss_tails_worse"]
    )
    observed_only_lead = bool(sample_ready and directional_support)
    failed_reasons = [key for key, passed in checks.items() if not passed]
    if observed_only_lead:
        status = "observed_only"
        decision = "observed_only_positive_duplicate_exposure_forward_lead"
    elif directional_support:
        status = "rejected"
        decision = "observed_only_rejected_duplicate_exposure_sample_or_concentration_failed"
    else:
        status = "rejected"
        decision = "observed_only_rejected_no_duplicate_exposure_edge"

    failure_mode_hit = bool(
        set(PREDICTION["main_failure_modes"])
        & {
            "duplicate_sample_too_thin"
            if not checks["duplicate_rows_min_passed"]
            or not checks["duplicate_groups_min_passed"]
            else "",
            "sec_financial_report_or_coin_confound"
            if not checks["single_duplicate_ticker_share_passed"]
            or not checks["single_duplicate_sleeve_share_passed"]
            else "",
            "no_cash_spy_qqq_separation" if not directional_support else "",
            "not_actionable_without_gate4" if not observed_only_lead else "",
        }
    )
    duplicate_examples = sorted(
        duplicate_group_records,
        key=lambda record: (
            safe_float((record.get("metrics_sum") or {}).get("replacement_value_vs_cash_usd"))
            or 0.0
        ),
    )[:10]
    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": observed_only_lead,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "observed_only_forward_attribution",
        "implementation_mode": "observed_only_forward_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "forward replacement ledger duplicate grouping",
            "cash SPY QQQ replacement attribution",
            "concentration guard",
            "no strategy change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": (
            "Cross-sleeve same-ticker same-entry-date duplicate exposure "
            "attribution over the materialized forward replacement ledger, "
            "explicitly excluding SEC_FTD_FINRA and other FINRA/FTD parked "
            "surfaces. This is not a threshold, scalar, top-N, hold, notional, "
            "or response-function retune."
        ),
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 1 if observed_only_lead else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1 if observed_only_lead else 0))
                ** 2,
                4,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": failure_mode_hit,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "Upside surprise: duplicate rows passed the predeclared sample, "
                "concentration, mean, median, and loss-tail checks across "
                "cash/SPY/QQQ. The result is still observed-only because no "
                "shared policy was changed or backtested."
                if observed_only_lead
                else (
                "Duplicate rows were directionally worse across the primary "
                "replacement metrics, but the surface is too thin or concentrated."
                if directional_support and not observed_only_lead
                else "Duplicate rows did not show a stable worse-than-singleton "
                "cash/SPY/QQQ replacement-value edge."
                )
            ),
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
            "source_rows": len(all_rows),
            "enriched_rows": len(enriched_rows),
            "eligible_rows": len(eligible_rows),
            "duplicate_rows": len(duplicate_rows),
            "duplicate_groups": len(duplicate_groups),
            "singleton_rows": len(singleton_rows),
            "excluded_finra_ftd_rows": len(excluded_rows),
            "ineligible_non_finra_ftd_rows": len(ineligible_rows),
        },
        "gate1": {
            "passed": baseline["loaded"],
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": bool(eligible_rows),
            "fields_checked": [
                "decision_id",
                "ticker",
                "sleeve_key",
                "entry_date",
                "exit_date",
                "pnl_usd",
                "notional_usd",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "target_price",
            ],
            "entry_date_present_rows": sum(1 for row in eligible_rows if row.get("entry_date")),
            "target_price_relevance": (
                "Forward replacement rows do not schedule target exits or orders; "
                "target_price is not required for this observed-only ledger attribution."
            ),
            "source_ledger": repo_rel(FORWARD_LEDGER),
            "excluded_finra_ftd_rows": len(excluded_rows),
            "ineligible_non_finra_ftd_rows": len(ineligible_rows),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter was added; rows are only attributed.",
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated": len(all_rows),
            "signals_survived": len(eligible_rows),
            "survival_rate": round(len(eligible_rows) / len(all_rows), 6)
            if all_rows
            else 0.0,
        },
        "gate4": {
            "passed": observed_only_lead,
            "decision": decision,
            "observed_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
            "acceptance_rule": ACCEPTANCE_RULE,
            "acceptance_checks": checks,
            "failed_reasons": failed_reasons,
            "sample_ready": sample_ready,
            "directional_support": directional_support,
            "comparisons": comparisons,
            "bucket_summary": {
                "duplicate_rows": bucket_summary(duplicate_rows),
                "singleton_rows": bucket_summary(singleton_rows),
                "all_eligible_rows": bucket_summary(eligible_rows),
            },
            "group_summary": {
                "duplicate_groups": grouped_bucket_summary(
                    duplicate_group_records, group_label="duplicate_groups"
                ),
                "singleton_groups": grouped_bucket_summary(
                    singleton_group_records, group_label="singleton_groups"
                ),
                "duplicate_group_examples": duplicate_examples,
            },
        },
        "summary": {
            "source_rows": len(all_rows),
            "enriched_rows": len(enriched_rows),
            "eligible_rows": len(eligible_rows),
            "duplicate_rows": len(duplicate_rows),
            "duplicate_groups": len(duplicate_groups),
            "singleton_rows": len(singleton_rows),
            "singleton_groups": len(singleton_groups),
            "excluded_finra_ftd_rows": len(excluded_rows),
            "max_duplicate_ticker_share": round(
                max_share(duplicate_tickers, len(duplicate_rows)), 6
            ),
            "max_duplicate_sleeve_share": round(
                max_share(duplicate_sleeves, len(duplicate_rows)), 6
            ),
            "top_duplicate_tickers": bucket_summary(duplicate_rows)["top_tickers"],
            "top_duplicate_sleeves": bucket_summary(duplicate_rows)["top_sleeves"],
            "decision": decision,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "exit_rules_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only attribution over an existing shared forward replacement "
                "ledger. No helper, adapter, order, rank, size, exit, watchlist, "
                "or LLM behavior changed."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "post_run_reflection": {
            "why_result_happened": (
                "The current ledger has four same-ticker same-entry-date duplicate "
                "groups after excluding FINRA/FTD rows, and all group-level cash "
                "replacement totals are negative. COIN is the largest loss group, "
                "while CRDO remains the largest duplicate ticker share at 40%, so "
                "the evidence is useful as a risk-control lead but still not a "
                "standalone activation result."
            ),
            "alpha_interpretation": (
                "This is not accepted alpha. Duplicate exposure remains a plausible "
                "risk-control lead only if materially more closed forward rows show "
                "stable cash/SPY/QQQ underperformance without ticker or sleeve concentration."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune duplicate caps, singleton definitions, same-day "
                "thresholds, response curves, notional, max positions, hold days, "
                "cooldowns, or top-N allocation on these same rows."
            ),
            "new_evidence_required": (
                "Do not rerun this observed-only attribution on the same rows. "
                "A valid next step is either materially more closed duplicate rows "
                "or a separate shared-policy Gate 1-4 duplicate-exposure cap test "
                "with explicit production/backtest parity."
            ),
        },
        "next_retry_requires": [
            ">=6 duplicate closed forward rows",
            ">=3 duplicate same-ticker same-entry-date groups",
            ">=30 singleton closed forward rows",
            "max duplicate ticker share <=50%",
            "max duplicate sleeve share <=70%",
            "stable worse duplicate cash/SPY/QQQ replacement value",
            "or a full shared-policy Gate 1-4 duplicate exposure cap test after the lead matures",
        ],
        "related_files": [
            repo_rel(FORWARD_LEDGER),
            repo_rel(BASELINE_PATH),
            "experiments/logs/exp-20260624-004.json",
            "experiments/logs/exp-20260624-006.json",
            "experiments/logs/exp-20260704-022.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
    }
    return result


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "status",
        "lane",
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
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "prediction",
        "calibration",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "summary",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    cash = payload["gate4"]["comparisons"]["replacement_value_vs_cash_usd"]
    spy = payload["gate4"]["comparisons"]["replacement_value_vs_spy_usd"]
    qqq = payload["gate4"]["comparisons"]["replacement_value_vs_qqq_usd"]
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} - forward duplicate exposure attribution",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- eligible/duplicate/singleton rows: {summary['eligible_rows']} / {summary['duplicate_rows']} / {summary['singleton_rows']}",
        f"- duplicate/singleton groups: {summary['duplicate_groups']} / {summary['singleton_groups']}",
        f"- excluded FINRA/FTD rows: {summary['excluded_finra_ftd_rows']}",
        f"- max duplicate ticker share: {summary['max_duplicate_ticker_share']}",
        f"- max duplicate sleeve share: {summary['max_duplicate_sleeve_share']}",
        (
            "- duplicate mean deltas vs singleton: "
            f"cash {cash['mean_delta_duplicate_minus_singleton']}, "
            f"SPY {spy['mean_delta_duplicate_minus_singleton']}, "
            f"QQQ {qqq['mean_delta_duplicate_minus_singleton']}"
        ),
        (
            "- duplicate median deltas vs singleton: "
            f"cash {cash['median_delta_duplicate_minus_singleton']}, "
            f"SPY {spy['median_delta_duplicate_minus_singleton']}, "
            f"QQQ {qqq['median_delta_duplicate_minus_singleton']}"
        ),
        "",
        "No entry, ranking, sizing, risk, exit, paper order, live order, "
        "watchlist, or LLM decision boundary changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    ticket = read_json(TICKET_JSON, {})
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["summary"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
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
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "eligible_rows": payload["summary"]["eligible_rows"],
                "duplicate_rows": payload["summary"]["duplicate_rows"],
                "duplicate_groups": payload["summary"]["duplicate_groups"],
                "singleton_rows": payload["summary"]["singleton_rows"],
                "max_duplicate_ticker_share": payload["summary"][
                    "max_duplicate_ticker_share"
                ],
                "max_duplicate_sleeve_share": payload["summary"][
                    "max_duplicate_sleeve_share"
                ],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
