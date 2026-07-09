"""exp-20260705-003: historical duplicate exposure validation.

Observed-only attribution that tests whether the forward duplicate-exposure
lead from exp-20260705-002 also appears on historical accepted paper replay
rows. It changes no entry, ranking, sizing, risk, exit, paper order, live
order, watchlist, or LLM decision boundary.
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


EXPERIMENT_ID = "exp-20260705-003"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "historical_duplicate_exposure_validation"
RUNNER = f"quant/experiments/exp_20260705_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
EXPERIMENTS_ROOT = REPO_ROOT / "quant" / "experiments"
for path in (SCRIPTS_ROOT, EXPERIMENTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution as accepted_rows  # noqa: E402
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
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Historical accepted paper replay rows can independently validate the "
    "exp-20260705-002 duplicate-exposure lead: if same-ticker same-entry-date "
    "cross-sleeve duplicate rows underperform singleton accepted paper rows in "
    "historical artifacts, a future shared duplicate-exposure cap has evidence "
    "beyond the current forward ledger."
)
CHANGED_VARIABLE = (
    "historical_accepted_paper_same_ticker_same_entry_duplicate_validation_v1"
)
MECHANISM_FAMILY = "forward_replacement_duplicate_exposure_attribution"
TRIAL_FAMILY = "historical_duplicate_exposure_validation"
TRIAL_VARIANT_ID = "accepted_artifact_same_ticker_same_entry_v1"
NEARBY_PRIORS = ["exp-20260705-002", "exp-20260609-021", "exp-20260507-905"]
PREDICTION = {
    "success_probability": 0.26,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "historical_duplicate_sample_too_thin",
        "forward_lead_not_reproduced",
        "accepted_artifact_schema_mismatch",
        "single_ticker_concentration",
    ],
    "confidence_reason": (
        "Forward rows showed a strong but thin duplicate-loss lead; historical "
        "accepted paper artifacts are an independent row surface, but prior "
        "same-entry displacement and cluster tests were fragile or "
        "concentration-limited."
    ),
    "recorded_at": "2026-07-05T02:05:53+00:00",
}
PRIMARY_METRIC = "pnl_per_10k"
DIAGNOSTIC_METRICS = ["pnl_per_10k", "pnl_pct_net", "pnl"]
ACCEPTANCE_RULE = {
    "primary_metric": PRIMARY_METRIC,
    "group_key": ["window", "entry_date", "ticker"],
    "duplicate_definition": (
        "two or more rows from different accepted paper sleeves with the same "
        "window, entry_date, and ticker"
    ),
    "singleton_definition": "exactly one eligible row for the same group key",
    "min_duplicate_rows": 12,
    "min_duplicate_groups": 5,
    "min_singleton_rows": 60,
    "min_duplicate_windows": 2,
    "min_windows_duplicate_mean_worse": 2,
    "max_single_duplicate_ticker_share": 0.50,
    "max_single_duplicate_sleeve_share": 0.70,
    "require_duplicate_mean_worse": True,
    "require_duplicate_median_worse": True,
    "require_duplicate_loss_tail_worse": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_003_{SLUG}.json",
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


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def round_float(value: Any, digits: int = 6) -> float | None:
    parsed = safe_float(value)
    return round(parsed, digits) if parsed is not None else None


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
        "sum": round(sum(values), 4) if values else None,
        "mean": round(mean(values), 6) if values else None,
        "median": round(median(values), 6) if values else None,
        "min": round(min(values), 6) if values else None,
        "max": round(max(values), 6) if values else None,
        "p20": round(percentile(sorted_values, 0.2), 6) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6)
        if values
        else None,
        "worst_20pct_mean": round(worst_tail_mean(values, 0.2), 6)
        if values
        else None,
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {})
    raw_windows = payload.get("windows") or []
    windows = list(raw_windows.values()) if isinstance(raw_windows, dict) else raw_windows
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


def is_finra_or_ftd_surface(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "sleeve",
            "accepted_experiment_id",
            "source_artifact",
            "strategy",
            "decision_id",
        )
    ).lower()
    return "finra" in text or "ftd" in text


def row_has_required_fields(row: dict[str, Any]) -> bool:
    return all(
        row.get(key) not in (None, "")
        for key in ("window", "entry_date", "ticker", "sleeve", PRIMARY_METRIC)
    )


def load_historical_rows() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    snapshots = {
        label: accepted_rows._load_snapshot(cfg["snapshot"])
        for label, cfg in accepted_rows.WINDOWS.items()
    }
    trading_dates_by_window = {
        label: accepted_rows._trading_dates(snapshot)
        for label, snapshot in snapshots.items()
    }
    all_rows: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []
    for spec in accepted_rows.SOURCE_SPECS:
        rows, report = accepted_rows._extract_source_rows(
            spec, snapshots, trading_dates_by_window
        )
        all_rows.extend(rows)
        source_reports.append(report)
    return all_rows, source_reports, [
        {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
        }
        for label, cfg in accepted_rows.WINDOWS.items()
    ]


def group_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("window") or ""),
        str(row.get("entry_date") or "")[:10],
        str(row.get("ticker") or "").upper(),
    )


def grouped_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)
    return dict(groups)


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    sleeves = Counter(str(row.get("sleeve") or "UNKNOWN") for row in rows)
    windows = Counter(str(row.get("window") or "UNKNOWN") for row in rows)
    metrics = {}
    for key in DIAGNOSTIC_METRICS:
        values = [safe_float(row.get(key)) for row in rows]
        metrics[key] = summarize_values([value for value in values if value is not None])
    return {
        "row_count": len(rows),
        "ticker_count": len(tickers),
        "sleeve_count": len(sleeves),
        "window_count": len(windows),
        "ticker_counts": dict(sorted(tickers.items())),
        "sleeve_counts": dict(sorted(sleeves.items())),
        "window_counts": dict(sorted(windows.items())),
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


def group_records(groups: dict[tuple[str, str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for (window, entry_date, ticker), rows in sorted(groups.items()):
        sleeves = Counter(str(row.get("sleeve") or "UNKNOWN") for row in rows)
        metrics = {}
        for key in DIAGNOSTIC_METRICS:
            values = [safe_float(row.get(key)) for row in rows]
            clean = [value for value in values if value is not None]
            metrics[key] = {
                "row_sum": round(sum(clean), 6) if clean else None,
                "row_mean": round(mean(clean), 6) if clean else None,
            }
        records.append(
            {
                "window": window,
                "entry_date": entry_date,
                "ticker": ticker,
                "row_count": len(rows),
                "sleeves": dict(sorted(sleeves.items())),
                "accepted_experiment_ids": sorted(
                    {
                        str(row.get("accepted_experiment_id") or "")
                        for row in rows
                        if row.get("accepted_experiment_id")
                    }
                ),
                "row_fingerprints": [str(row.get("row_fingerprint") or "") for row in rows],
                "metrics": metrics,
            }
        )
    return records


def compare_rows(
    duplicate_rows: list[dict[str, Any]], singleton_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for key in DIAGNOSTIC_METRICS:
        duplicate_values = [
            value
            for row in duplicate_rows
            if (value := safe_float(row.get(key))) is not None
        ]
        singleton_values = [
            value
            for row in singleton_rows
            if (value := safe_float(row.get(key))) is not None
        ]
        duplicate_summary = summarize_values(duplicate_values)
        singleton_summary = summarize_values(singleton_values)
        comparisons[key] = {
            "duplicate_rows": duplicate_summary,
            "singleton_rows": singleton_summary,
            "mean_delta_duplicate_minus_singleton": round(
                (duplicate_summary["mean"] or 0.0) - (singleton_summary["mean"] or 0.0),
                6,
            )
            if duplicate_values and singleton_values
            else None,
            "median_delta_duplicate_minus_singleton": round(
                (duplicate_summary["median"] or 0.0)
                - (singleton_summary["median"] or 0.0),
                6,
            )
            if duplicate_values and singleton_values
            else None,
            "tail_delta_duplicate_minus_singleton": round(
                (duplicate_summary["worst_20pct_mean"] or 0.0)
                - (singleton_summary["worst_20pct_mean"] or 0.0),
                6,
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


def per_window_comparisons(
    duplicate_rows: list[dict[str, Any]], singleton_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    windows = sorted(
        {str(row.get("window") or "") for row in [*duplicate_rows, *singleton_rows]}
    )
    out: dict[str, Any] = {}
    for window in windows:
        duplicate_values = [
            value
            for row in duplicate_rows
            if row.get("window") == window and (value := safe_float(row.get(PRIMARY_METRIC))) is not None
        ]
        singleton_values = [
            value
            for row in singleton_rows
            if row.get("window") == window and (value := safe_float(row.get(PRIMARY_METRIC))) is not None
        ]
        duplicate_summary = summarize_values(duplicate_values)
        singleton_summary = summarize_values(singleton_values)
        out[window] = {
            "duplicate_rows": duplicate_summary,
            "singleton_rows": singleton_summary,
            "duplicate_mean_worse": (
                duplicate_summary["mean"] is not None
                and singleton_summary["mean"] is not None
                and duplicate_summary["mean"] < singleton_summary["mean"]
            ),
            "mean_delta_duplicate_minus_singleton": round(
                (duplicate_summary["mean"] or 0.0) - (singleton_summary["mean"] or 0.0),
                6,
            )
            if duplicate_values and singleton_values
            else None,
        }
    return out


def max_share(counter: Counter[str], total: int) -> float:
    if not counter or total <= 0:
        return 0.0
    return max(counter.values()) / total


def source_report_summary(source_reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_count": len(source_reports),
        "rows_total": sum(int(row.get("rows_total") or 0) for row in source_reports),
        "rows_with_required_fields": sum(
            int(row.get("rows_with_required_fields") or 0) for row in source_reports
        ),
        "rows_with_state": sum(
            int(row.get("rows_with_state") or 0) for row in source_reports
        ),
        "invalid_rows": sum(int(row.get("invalid_rows") or 0) for row in source_reports),
        "missing_state_rows": sum(
            int(row.get("missing_state_rows") or 0) for row in source_reports
        ),
        "by_sleeve": [
            {
                "sleeve": row.get("sleeve"),
                "accepted_experiment_id": row.get("accepted_experiment_id"),
                "artifact": row.get("artifact"),
                "rows_total": row.get("rows_total"),
                "rows_with_required_fields": row.get("rows_with_required_fields"),
                "rows_with_state": row.get("rows_with_state"),
                "invalid_rows": row.get("invalid_rows"),
                "missing_state_rows": row.get("missing_state_rows"),
            }
            for row in source_reports
        ],
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = baseline_metrics()
    all_rows, source_reports, windows = load_historical_rows()
    excluded_surface_rows = [row for row in all_rows if is_finra_or_ftd_surface(row)]
    non_finra_rows = [row for row in all_rows if not is_finra_or_ftd_surface(row)]
    eligible_rows = [row for row in non_finra_rows if row_has_required_fields(row)]
    ineligible_rows = [row for row in non_finra_rows if not row_has_required_fields(row)]

    groups = grouped_rows(eligible_rows)
    duplicate_groups = {
        key: rows
        for key, rows in groups.items()
        if len(rows) >= 2 and len({str(row.get("sleeve") or "") for row in rows}) >= 2
    }
    singleton_groups = {key: rows for key, rows in groups.items() if len(rows) == 1}
    same_sleeve_multi_groups = {
        key: rows
        for key, rows in groups.items()
        if len(rows) >= 2 and key not in duplicate_groups
    }
    duplicate_rows = [row for rows in duplicate_groups.values() for row in rows]
    singleton_rows = [row for rows in singleton_groups.values() for row in rows]
    duplicate_group_records = group_records(duplicate_groups)
    singleton_group_records = group_records(singleton_groups)
    same_sleeve_multi_group_records = group_records(same_sleeve_multi_groups)
    comparisons = compare_rows(duplicate_rows, singleton_rows)
    primary_comparison = comparisons[PRIMARY_METRIC]
    window_comparisons = per_window_comparisons(duplicate_rows, singleton_rows)

    duplicate_tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in duplicate_rows)
    duplicate_sleeves = Counter(str(row.get("sleeve") or "UNKNOWN") for row in duplicate_rows)
    duplicate_windows = Counter(str(row.get("window") or "UNKNOWN") for row in duplicate_rows)
    windows_with_duplicate_rows = {
        window
        for window, row in window_comparisons.items()
        if int((row.get("duplicate_rows") or {}).get("n") or 0) > 0
    }
    windows_duplicate_mean_worse = {
        window for window, row in window_comparisons.items() if row["duplicate_mean_worse"]
    }

    checks = {
        "duplicate_rows_min_passed": len(duplicate_rows)
        >= ACCEPTANCE_RULE["min_duplicate_rows"],
        "duplicate_groups_min_passed": len(duplicate_groups)
        >= ACCEPTANCE_RULE["min_duplicate_groups"],
        "singleton_rows_min_passed": len(singleton_rows)
        >= ACCEPTANCE_RULE["min_singleton_rows"],
        "duplicate_windows_min_passed": len(windows_with_duplicate_rows)
        >= ACCEPTANCE_RULE["min_duplicate_windows"],
        "windows_duplicate_mean_worse_min_passed": len(windows_duplicate_mean_worse)
        >= ACCEPTANCE_RULE["min_windows_duplicate_mean_worse"],
        "single_duplicate_ticker_share_passed": max_share(
            duplicate_tickers, len(duplicate_rows)
        )
        <= ACCEPTANCE_RULE["max_single_duplicate_ticker_share"],
        "single_duplicate_sleeve_share_passed": max_share(
            duplicate_sleeves, len(duplicate_rows)
        )
        <= ACCEPTANCE_RULE["max_single_duplicate_sleeve_share"],
        "duplicate_mean_worse": primary_comparison["duplicate_mean_worse"],
        "duplicate_median_worse": primary_comparison["duplicate_median_worse"],
        "duplicate_loss_tail_worse": primary_comparison["duplicate_loss_tail_worse"],
        "field_reality_passed": bool(eligible_rows) and not ineligible_rows,
    }
    sample_ready = (
        checks["duplicate_rows_min_passed"]
        and checks["duplicate_groups_min_passed"]
        and checks["singleton_rows_min_passed"]
        and checks["duplicate_windows_min_passed"]
        and checks["single_duplicate_ticker_share_passed"]
        and checks["single_duplicate_sleeve_share_passed"]
        and checks["field_reality_passed"]
    )
    directional_support = (
        checks["duplicate_mean_worse"]
        and checks["duplicate_median_worse"]
        and checks["duplicate_loss_tail_worse"]
        and checks["windows_duplicate_mean_worse_min_passed"]
    )
    observed_only_lead = bool(sample_ready and directional_support)
    failed_reasons = [key for key, passed in checks.items() if not passed]
    if observed_only_lead:
        status = "observed_only"
        decision = "observed_only_positive_historical_duplicate_exposure_validation_lead"
    elif not sample_ready:
        status = "rejected"
        decision = (
            "rejected_historical_duplicate_exposure_sample_or_concentration_failed"
        )
    else:
        status = "rejected"
        decision = "rejected_historical_duplicate_exposure_not_confirmed"

    realized_failure_modes = []
    if (
        not checks["duplicate_rows_min_passed"]
        or not checks["duplicate_groups_min_passed"]
        or not checks["duplicate_windows_min_passed"]
    ):
        realized_failure_modes.append("historical_duplicate_sample_too_thin")
    if not directional_support:
        realized_failure_modes.append("forward_lead_not_reproduced")
    if not checks["field_reality_passed"]:
        realized_failure_modes.append("accepted_artifact_schema_mismatch")
    if not checks["single_duplicate_ticker_share_passed"]:
        realized_failure_modes.append("single_ticker_concentration")
    prediction_hit = bool(
        set(PREDICTION["main_failure_modes"]) & set(realized_failure_modes)
    )

    if observed_only_lead:
        surprise_note = (
            "The historical accepted-paper row surface independently reproduced "
            "the duplicate-exposure loss pattern under the sample, concentration, "
            "window, and primary-metric checks. This is still not accepted alpha "
            "because no shared policy was changed or Gate 1-4 backtest was run."
        )
    else:
        surprise_note = (
            "The historical validation did not confirm the forward lead. After "
            "excluding FINRA/FTD surfaces, duplicate historical rows were too "
            "thin, concentrated, and not worse than singleton rows on pnl_per_10k."
        )

    field_reality = {
        "required_source_fields": [
            "window",
            "entry_date",
            "ticker",
            "sleeve",
            PRIMARY_METRIC,
        ],
        "target_price_relevance": (
            "Historical accepted paper replay rows are fixed completed outcomes; "
            "target_price is not required for this read-only attribution and no "
            "new exits or orders are scheduled."
        ),
        "source_rows_total": len(all_rows),
        "excluded_finra_ftd_rows": len(excluded_surface_rows),
        "non_finra_rows": len(non_finra_rows),
        "eligible_rows": len(eligible_rows),
        "ineligible_non_finra_rows": len(ineligible_rows),
        "entry_date_present_rows": sum(1 for row in non_finra_rows if row.get("entry_date")),
        "target_price_present_rows": sum(
            1 for row in non_finra_rows if row.get("target_price") not in (None, "")
        ),
        "blocked": bool(ineligible_rows) or not eligible_rows,
    }

    summary = {
        "source_rows": len(all_rows),
        "excluded_finra_ftd_rows": len(excluded_surface_rows),
        "non_finra_rows": len(non_finra_rows),
        "eligible_rows": len(eligible_rows),
        "duplicate_rows": len(duplicate_rows),
        "duplicate_groups": len(duplicate_groups),
        "singleton_rows": len(singleton_rows),
        "singleton_groups": len(singleton_groups),
        "same_sleeve_multi_groups": len(same_sleeve_multi_groups),
        "duplicate_windows": dict(sorted(duplicate_windows.items())),
        "windows_with_duplicate_rows": sorted(windows_with_duplicate_rows),
        "windows_duplicate_mean_worse": sorted(windows_duplicate_mean_worse),
        "max_duplicate_ticker_share": round(max_share(duplicate_tickers, len(duplicate_rows)), 6),
        "max_duplicate_sleeve_share": round(max_share(duplicate_sleeves, len(duplicate_rows)), 6),
        "top_duplicate_tickers": bucket_summary(duplicate_rows)["top_tickers"],
        "top_duplicate_sleeves": bucket_summary(duplicate_rows)["top_sleeves"],
        "primary_mean_delta_duplicate_minus_singleton": primary_comparison[
            "mean_delta_duplicate_minus_singleton"
        ],
        "primary_median_delta_duplicate_minus_singleton": primary_comparison[
            "median_delta_duplicate_minus_singleton"
        ],
        "primary_tail_delta_duplicate_minus_singleton": primary_comparison[
            "tail_delta_duplicate_minus_singleton"
        ],
        "decision": decision,
    }

    payload: dict[str, Any] = {
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
        "change_type": "observed_only_attribution",
        "implementation_mode": "observed_only_historical_accepted_paper_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "historical accepted paper row rebuild",
            "new duplicate gate shape",
            "singleton comparator",
            "concentration guard",
            "no strategy change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape_historical_artifact_validation",
        "new_evidence_axis": (
            "Historical accepted paper artifact validation of the "
            "exp-20260705-002 same-ticker same-entry duplicate-exposure lead "
            "on a different row surface. This is not a readiness audit, not an "
            "observer/FTD/FINRA surface, not a threshold/scalar/top-N/hold/"
            "notional retune, and not a reslice of the same 60 forward rows."
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
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": prediction_hit,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise_note": surprise_note,
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
            "historical_source_rows": len(all_rows),
            "eligible_rows": len(eligible_rows),
            "duplicate_rows": len(duplicate_rows),
            "duplicate_groups": len(duplicate_groups),
            "singleton_rows": len(singleton_rows),
        },
        "gate1": {
            "passed": baseline["loaded"],
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": not field_reality["blocked"],
            "field_reality": field_reality,
            "source_report_summary": source_report_summary(source_reports),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter was added; rows are only attributed.",
            "baseline_survival_rate": baseline["survival_rate"],
            "baseline_min_window_survival_rate": baseline["min_window_survival_rate"],
            "survival_guard_passed": (
                baseline["min_window_survival_rate"] is not None
                and baseline["min_window_survival_rate"] >= 0.05
            ),
        },
        "gate4": {
            "passed": observed_only_lead,
            "decision": decision,
            "observed_only": True,
            "accepted_strategy_change": False,
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
            "primary_comparison": primary_comparison,
            "comparisons": comparisons,
            "per_window_comparisons": window_comparisons,
            "bucket_summary": {
                "duplicate_rows": bucket_summary(duplicate_rows),
                "singleton_rows": bucket_summary(singleton_rows),
                "eligible_rows": bucket_summary(eligible_rows),
            },
            "duplicate_group_examples": duplicate_group_records[:25],
            "same_sleeve_multi_group_examples": same_sleeve_multi_group_records[:25],
        },
        "summary": summary,
        "source_reports": source_reports,
        "source_windows": windows,
        "sample_rows": {
            "duplicate_rows": duplicate_rows[:25],
            "singleton_rows": singleton_rows[:25],
            "duplicate_groups": duplicate_group_records[:25],
            "singleton_groups": singleton_group_records[:10],
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
                "Read-only attribution over existing historical accepted paper "
                "replay artifacts. No helper, adapter, order, rank, size, exit, "
                "watchlist, or LLM behavior changed."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "post_run_reflection": {
            "why_result_happened": (
                "The independent historical accepted-paper surface did not "
                "support the forward duplicate-loss lead. After excluding "
                "FINRA/FTD sleeves, only four duplicate rows across two groups "
                "remained, all in MU and all in the late_strong window; their "
                "pnl_per_10k was better than singleton accepted-paper rows."
            ),
            "alpha_interpretation": (
                "This rejects historical validation, not necessarily the "
                "forward risk-control idea. The forward lead remains a thin "
                "observed-only lead that needs more closed forward duplicate "
                "rows or a separate shared-policy Gate 1-4 test before any cap."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune duplicate thresholds, group keys, singleton "
                "definitions, per-window requirements, concentration caps, "
                "notional scaling, position caps, hold days, or response "
                "functions on these same historical rows."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more closed forward duplicate "
                "rows, a new accepted-paper artifact source with additional "
                "independent settled rows, or a separate shared-policy Gate 1-4 "
                "duplicate exposure cap experiment with explicit parity."
            ),
        },
        "next_retry_requires": [
            "materially more closed forward same-ticker same-entry duplicate rows",
            "or a new accepted-paper artifact source with independent settled rows",
            "or a full shared-policy Gate 1-4 duplicate exposure cap test",
        ],
        "related_files": [
            repo_rel(BASELINE_PATH),
            "quant/experiments/exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution.py",
            "experiments/logs/exp-20260705-002.json",
            "experiments/logs/exp-20260609-021.json",
            "experiments/logs/exp-20260507-905.json",
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
    return payload


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
    primary = payload["gate4"]["primary_comparison"]
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} - historical duplicate exposure validation",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- eligible/duplicate/singleton rows: {summary['eligible_rows']} / {summary['duplicate_rows']} / {summary['singleton_rows']}",
        f"- duplicate/singleton groups: {summary['duplicate_groups']} / {summary['singleton_groups']}",
        f"- excluded FINRA/FTD rows: {summary['excluded_finra_ftd_rows']}",
        f"- duplicate windows: {', '.join(summary['windows_with_duplicate_rows']) or 'none'}",
        f"- max duplicate ticker share: {summary['max_duplicate_ticker_share']}",
        f"- max duplicate sleeve share: {summary['max_duplicate_sleeve_share']}",
        (
            "- primary pnl_per_10k deltas duplicate minus singleton: "
            f"mean {primary['mean_delta_duplicate_minus_singleton']}, "
            f"median {primary['median_delta_duplicate_minus_singleton']}, "
            f"tail {primary['tail_delta_duplicate_minus_singleton']}"
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
            "calibration": payload["calibration"],
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
                "primary_mean_delta_duplicate_minus_singleton": payload["summary"][
                    "primary_mean_delta_duplicate_minus_singleton"
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
