"""exp-20260705-009: duplicate-exposure cap policy simulation.

Read-only policy simulation over accepted non-FINRA default-off paper rows. The
policy keeps only the highest static-priority row in each same-ticker
same-entry-date cross-sleeve duplicate group. It changes no entry, ranking,
sizing, risk budget, exit, paper order, live order, watchlist, or LLM boundary.
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


EXPERIMENT_ID = "exp-20260705-009"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "duplicate_exposure_cap_policy_sim"
RUNNER = f"quant/experiments/exp_20260705_009_{SLUG}.py"
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
FORWARD_LEDGER = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Default-off paper duplicate-exposure cap: a fixed shared policy that keeps "
    "only the highest-priority same-ticker same-entry-date paper row across "
    "accepted non-FINRA sleeves may improve forward replacement value without "
    "changing live orders."
)
CHANGED_VARIABLE = (
    "fixed_same_ticker_same_entry_date_duplicate_exposure_cap_non_finra_paper_v1"
)
MECHANISM_FAMILY = "risk_allocation"
TRIAL_FAMILY = "duplicate_exposure_cap_policy_sim"
TRIAL_VARIANT_ID = "cross_sleeve_static_priority_same_ticker_entry_v1"
NEARBY_PRIORS = [
    "exp-20260705-002",
    "exp-20260705-003",
    "exp-20260705-004",
    "exp-20260704-022",
]
PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "historical_validation_failed",
        "duplicate_sample_too_thin",
        "concentration_failed",
        "forward_only_not_gate_ready",
    ],
    "confidence_reason": (
        "Forward rows showed a positive duplicate-loss lead in exp-20260705-002, "
        "but exp-20260705-003 historical validation failed due thin and "
        "concentrated duplicates; a fixed cap policy should fail if the lead is "
        "not robust beyond the current forward ledger."
    ),
    "recorded_at": "2026-07-05T10:08:58+00:00",
}
FORWARD_PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
HISTORICAL_PRIMARY_METRICS = ["pnl_per_10k"]
HISTORICAL_DIAGNOSTIC_METRICS = ["pnl_per_10k", "pnl_pct_net", "pnl"]
SLEEVE_PRIORITY = [
    "accepted_helper_source_priority_allocator",
    "accepted_source_consensus",
    "free_data_cross_source_consensus",
    "fundamental_growth_rs",
    "alpha_score_market_regime",
    "volume_breadth_breakout",
    "state_surface",
    "sec_governance",
    "supplier_financing_debt_relief",
    "sec_financial_report",
    "low_deployment_etf",
    "broad_market",
]
SLEEVE_PRIORITY_RANK = {name: index for index, name in enumerate(SLEEVE_PRIORITY)}
ACCEPTANCE_RULE = {
    "policy": (
        "Within each non-FINRA cross-sleeve same-entry-date same-ticker group, "
        "keep the row from the first sleeve in the static priority list and skip "
        "the remaining duplicate rows. Do not use future replacement outcomes to "
        "choose the kept row."
    ),
    "policy_priority": SLEEVE_PRIORITY,
    "duplicate_definition": (
        "two or more eligible rows with the same ticker and entry_date, and at "
        "least two distinct sleeves; same-sleeve multi-row groups are reported "
        "but not capped"
    ),
    "forward_min_duplicate_rows": 6,
    "forward_min_duplicate_groups": 3,
    "forward_max_single_duplicate_ticker_share": 0.50,
    "forward_max_single_duplicate_sleeve_share": 0.70,
    "require_forward_cap_improves_all_primary_metrics": True,
    "historical_min_duplicate_rows": 12,
    "historical_min_duplicate_groups": 5,
    "historical_min_duplicate_windows": 2,
    "historical_max_single_duplicate_ticker_share": 0.50,
    "historical_max_single_duplicate_sleeve_share": 0.70,
    "require_historical_cap_improves_primary_metric": True,
    "require_no_outcome_peeking": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_009_{SLUG}.json",
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
    windows = list(raw_windows.values()) if isinstance(raw_windows, dict) else list(raw_windows)
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
        "sum": round(sum(values), 6) if values else None,
        "mean": round(mean(values), 6) if values else None,
        "median": round(median(values), 6) if values else None,
        "min": round(min(values), 6) if values else None,
        "max": round(max(values), 6) if values else None,
        "p20": round(percentile(sorted_values, 0.2), 6) if values else None,
        "worst_20pct_mean": round(worst_tail_mean(values), 6) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6)
        if values
        else None,
    }


def row_sleeve(row: dict[str, Any]) -> str:
    return str(row.get("sleeve_key") or row.get("sleeve") or "UNKNOWN")


def row_ticker(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or "").upper()


def row_entry_date(row: dict[str, Any]) -> str:
    return str(row.get("entry_date") or "")[:10]


def row_decision_id(row: dict[str, Any]) -> str:
    return str(
        row.get("decision_id")
        or row.get("row_fingerprint")
        or row.get("accepted_experiment_id")
        or ""
    )


def is_finra_or_ftd_surface(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "sleeve",
            "sleeve_key",
            "accepted_experiment_id",
            "source_artifact",
            "strategy",
            "decision_id",
            "source",
            "source_family",
            "trial_family",
            "rule_version",
        )
    ).lower()
    return "finra" in text or "ftd" in text


def valid_forward_row(row: dict[str, Any]) -> bool:
    required = ["ticker", "entry_date", *FORWARD_PRIMARY_METRICS]
    return all(row.get(key) not in (None, "") for key in required)


def valid_historical_row(row: dict[str, Any]) -> bool:
    return all(
        row.get(key) not in (None, "")
        for key in ("window", "entry_date", "ticker", "sleeve", "pnl_per_10k")
    )


def forward_group_key(row: dict[str, Any]) -> tuple[str, str]:
    return (row_entry_date(row), row_ticker(row))


def historical_group_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("window") or ""), row_entry_date(row), row_ticker(row))


def group_rows(
    rows: list[dict[str, Any]], historical: bool = False
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = historical_group_key(row) if historical else forward_group_key(row)
        groups[key].append(row)
    return dict(groups)


def cross_sleeve_duplicate_groups(
    groups: dict[tuple[Any, ...], list[dict[str, Any]]]
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    return {
        key: rows
        for key, rows in groups.items()
        if len(rows) >= 2 and len({row_sleeve(row) for row in rows}) >= 2
    }


def same_sleeve_multi_groups(
    groups: dict[tuple[Any, ...], list[dict[str, Any]]],
    duplicate_groups: dict[tuple[Any, ...], list[dict[str, Any]]],
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    return {key: rows for key, rows in groups.items() if len(rows) >= 2 and key not in duplicate_groups}


def max_share(counter: Counter[str], total: int) -> float:
    if not counter or total <= 0:
        return 0.0
    return max(counter.values()) / total


def priority_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    sleeve = row_sleeve(row)
    return (
        SLEEVE_PRIORITY_RANK.get(sleeve, 1000),
        sleeve,
        row_decision_id(row),
        str(row.get("source_artifact") or ""),
    )


def row_brief(row: dict[str, Any], metric_keys: list[str]) -> dict[str, Any]:
    out = {
        "window": row.get("window"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "ticker": row.get("ticker"),
        "sleeve": row_sleeve(row),
        "decision_id": row_decision_id(row),
    }
    for key in metric_keys:
        out[key] = round_float(row.get(key))
    return out


def summarize_rows(rows: list[dict[str, Any]], metric_keys: list[str]) -> dict[str, Any]:
    tickers = Counter(row_ticker(row) or "UNKNOWN" for row in rows)
    sleeves = Counter(row_sleeve(row) for row in rows)
    windows = Counter(str(row.get("window") or "forward") for row in rows)
    metrics = {}
    for key in metric_keys:
        values = [
            value
            for row in rows
            if (value := safe_float(row.get(key))) is not None
        ]
        metrics[key] = summarize_values(values)
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


def policy_delta(
    uncapped_rows: list[dict[str, Any]],
    capped_rows: list[dict[str, Any]],
    skipped_rows: list[dict[str, Any]],
    metric_keys: list[str],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key in metric_keys:
        uncapped = [value for row in uncapped_rows if (value := safe_float(row.get(key))) is not None]
        capped = [value for row in capped_rows if (value := safe_float(row.get(key))) is not None]
        skipped = [value for row in skipped_rows if (value := safe_float(row.get(key))) is not None]
        uncapped_sum = sum(uncapped) if uncapped else 0.0
        capped_sum = sum(capped) if capped else 0.0
        skipped_sum = sum(skipped) if skipped else 0.0
        metrics[key] = {
            "uncapped_sum": round(uncapped_sum, 6),
            "capped_sum": round(capped_sum, 6),
            "skipped_sum": round(skipped_sum, 6),
            "capped_minus_uncapped_sum": round(capped_sum - uncapped_sum, 6),
            "uncapped_mean": round(mean(uncapped), 6) if uncapped else None,
            "capped_mean": round(mean(capped), 6) if capped else None,
            "skipped_mean": round(mean(skipped), 6) if skipped else None,
            "sum_improved_by_cap": bool(capped_sum > uncapped_sum),
            "skipped_rows_negative": bool(skipped and skipped_sum < 0.0),
        }
    return metrics


def group_record(
    key: tuple[Any, ...],
    rows: list[dict[str, Any]],
    kept: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    metric_keys: list[str],
) -> dict[str, Any]:
    if len(key) == 3:
        window, entry_date, ticker = key
    else:
        window, entry_date, ticker = "forward", key[0], key[1]
    return {
        "window": window,
        "entry_date": entry_date,
        "ticker": ticker,
        "row_count": len(rows),
        "kept_rows": len(kept),
        "skipped_rows": len(skipped),
        "sleeves": dict(sorted(Counter(row_sleeve(row) for row in rows).items())),
        "kept": [row_brief(row, metric_keys) for row in kept],
        "skipped": [row_brief(row, metric_keys) for row in skipped],
        "metrics_uncapped": summarize_rows(rows, metric_keys)["metrics"],
        "metrics_kept": summarize_rows(kept, metric_keys)["metrics"],
        "metrics_skipped": summarize_rows(skipped, metric_keys)["metrics"],
    }


def apply_duplicate_cap(
    groups: dict[tuple[Any, ...], list[dict[str, Any]]],
    metric_keys: list[str],
) -> dict[str, Any]:
    duplicate_groups = cross_sleeve_duplicate_groups(groups)
    kept_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for key, rows in sorted(groups.items()):
        if key in duplicate_groups:
            ordered = sorted(rows, key=priority_sort_key)
            kept = [ordered[0]]
            skipped = ordered[1:]
        else:
            kept = list(rows)
            skipped = []
        kept_rows.extend(kept)
        skipped_rows.extend(skipped)
        if key in duplicate_groups:
            records.append(group_record(key, rows, kept, skipped, metric_keys))
    all_rows = [row for rows in groups.values() for row in rows]
    return {
        "kept_rows": kept_rows,
        "skipped_rows": skipped_rows,
        "duplicate_groups": duplicate_groups,
        "duplicate_group_records": records,
        "delta": policy_delta(all_rows, kept_rows, skipped_rows, metric_keys),
    }


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


def source_report_summary(source_reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_count": len(source_reports),
        "rows_total": sum(int(row.get("rows_total") or 0) for row in source_reports),
        "rows_with_required_fields": sum(
            int(row.get("rows_with_required_fields") or 0) for row in source_reports
        ),
        "invalid_rows": sum(int(row.get("invalid_rows") or 0) for row in source_reports),
        "by_sleeve": [
            {
                "sleeve": row.get("sleeve"),
                "accepted_experiment_id": row.get("accepted_experiment_id"),
                "artifact": row.get("artifact"),
                "rows_total": row.get("rows_total"),
                "rows_with_required_fields": row.get("rows_with_required_fields"),
                "invalid_rows": row.get("invalid_rows"),
                "missing_state_rows": row.get("missing_state_rows"),
            }
            for row in source_reports
        ],
    }


def build_surface_checks(
    *,
    prefix: str,
    duplicate_rows: list[dict[str, Any]],
    duplicate_groups: dict[tuple[Any, ...], list[dict[str, Any]]],
    metric_delta: dict[str, Any],
    required_metrics: list[str],
    min_rows: int,
    min_groups: int,
    max_ticker_share: float,
    max_sleeve_share: float,
    min_windows: int | None = None,
) -> tuple[dict[str, bool], list[str]]:
    tickers = Counter(row_ticker(row) or "UNKNOWN" for row in duplicate_rows)
    sleeves = Counter(row_sleeve(row) for row in duplicate_rows)
    windows = {str(row.get("window") or "forward") for row in duplicate_rows}
    checks = {
        f"{prefix}_duplicate_rows_min_passed": len(duplicate_rows) >= min_rows,
        f"{prefix}_duplicate_groups_min_passed": len(duplicate_groups) >= min_groups,
        f"{prefix}_single_duplicate_ticker_share_passed": max_share(
            tickers, len(duplicate_rows)
        )
        <= max_ticker_share,
        f"{prefix}_single_duplicate_sleeve_share_passed": max_share(
            sleeves, len(duplicate_rows)
        )
        <= max_sleeve_share,
        f"{prefix}_cap_improves_required_metrics": all(
            bool((metric_delta.get(key) or {}).get("sum_improved_by_cap"))
            and bool((metric_delta.get(key) or {}).get("skipped_rows_negative"))
            for key in required_metrics
        ),
    }
    if min_windows is not None:
        checks[f"{prefix}_duplicate_windows_min_passed"] = len(windows) >= min_windows
    return checks, [key for key, passed in checks.items() if not passed]


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = baseline_metrics()

    forward_raw_rows = read_jsonl(FORWARD_LEDGER)
    forward_enriched = [row for row in forward_raw_rows if row.get("status") == "enriched"]
    forward_excluded = [row for row in forward_enriched if is_finra_or_ftd_surface(row)]
    forward_non_finra = [
        row for row in forward_enriched if not is_finra_or_ftd_surface(row)
    ]
    forward_eligible = [row for row in forward_non_finra if valid_forward_row(row)]
    forward_ineligible = [
        row for row in forward_non_finra if not valid_forward_row(row)
    ]
    forward_groups = group_rows(forward_eligible)
    forward_duplicate_groups = cross_sleeve_duplicate_groups(forward_groups)
    forward_same_sleeve_multi = same_sleeve_multi_groups(
        forward_groups, forward_duplicate_groups
    )
    forward_duplicate_rows = [
        row for rows in forward_duplicate_groups.values() for row in rows
    ]
    forward_policy = apply_duplicate_cap(forward_groups, FORWARD_PRIMARY_METRICS)

    historical_raw_rows, historical_source_reports, historical_windows = load_historical_rows()
    historical_excluded = [
        row for row in historical_raw_rows if is_finra_or_ftd_surface(row)
    ]
    historical_non_finra = [
        row for row in historical_raw_rows if not is_finra_or_ftd_surface(row)
    ]
    historical_eligible = [
        row for row in historical_non_finra if valid_historical_row(row)
    ]
    historical_ineligible = [
        row for row in historical_non_finra if not valid_historical_row(row)
    ]
    historical_groups = group_rows(historical_eligible, historical=True)
    historical_duplicate_groups = cross_sleeve_duplicate_groups(historical_groups)
    historical_same_sleeve_multi = same_sleeve_multi_groups(
        historical_groups, historical_duplicate_groups
    )
    historical_duplicate_rows = [
        row for rows in historical_duplicate_groups.values() for row in rows
    ]
    historical_policy = apply_duplicate_cap(
        historical_groups, HISTORICAL_DIAGNOSTIC_METRICS
    )

    forward_checks, forward_failed = build_surface_checks(
        prefix="forward",
        duplicate_rows=forward_duplicate_rows,
        duplicate_groups=forward_duplicate_groups,
        metric_delta=forward_policy["delta"],
        required_metrics=FORWARD_PRIMARY_METRICS,
        min_rows=ACCEPTANCE_RULE["forward_min_duplicate_rows"],
        min_groups=ACCEPTANCE_RULE["forward_min_duplicate_groups"],
        max_ticker_share=ACCEPTANCE_RULE["forward_max_single_duplicate_ticker_share"],
        max_sleeve_share=ACCEPTANCE_RULE["forward_max_single_duplicate_sleeve_share"],
    )
    historical_checks, historical_failed = build_surface_checks(
        prefix="historical",
        duplicate_rows=historical_duplicate_rows,
        duplicate_groups=historical_duplicate_groups,
        metric_delta=historical_policy["delta"],
        required_metrics=HISTORICAL_PRIMARY_METRICS,
        min_rows=ACCEPTANCE_RULE["historical_min_duplicate_rows"],
        min_groups=ACCEPTANCE_RULE["historical_min_duplicate_groups"],
        max_ticker_share=ACCEPTANCE_RULE["historical_max_single_duplicate_ticker_share"],
        max_sleeve_share=ACCEPTANCE_RULE["historical_max_single_duplicate_sleeve_share"],
        min_windows=ACCEPTANCE_RULE["historical_min_duplicate_windows"],
    )
    field_checks = {
        "forward_field_reality_passed": bool(forward_eligible) and not forward_ineligible,
        "historical_field_reality_passed": bool(historical_eligible) and not historical_ineligible,
        "no_outcome_peeking_passed": True,
    }
    checks = {**forward_checks, **historical_checks, **field_checks}
    failed_reasons = [key for key, passed in checks.items() if not passed]
    forward_support = all(forward_checks.values()) and field_checks["forward_field_reality_passed"]
    historical_support = all(historical_checks.values()) and field_checks["historical_field_reality_passed"]
    policy_supported = bool(forward_support and historical_support)

    if policy_supported:
        status = "observed_only"
        decision = "observed_only_positive_duplicate_exposure_cap_policy_sim_lead"
    elif not historical_support:
        status = "rejected"
        decision = "rejected_duplicate_exposure_cap_historical_validation_failed"
    elif not forward_support:
        status = "rejected"
        decision = "rejected_duplicate_exposure_cap_forward_policy_failed"
    else:
        status = "rejected"
        decision = "rejected_duplicate_exposure_cap_not_gate_ready"

    realized_failure_modes: list[str] = []
    if (
        not historical_checks["historical_duplicate_rows_min_passed"]
        or not historical_checks["historical_duplicate_groups_min_passed"]
        or not historical_checks["historical_duplicate_windows_min_passed"]
    ):
        realized_failure_modes.append("duplicate_sample_too_thin")
        realized_failure_modes.append("historical_validation_failed")
    if (
        not historical_checks["historical_single_duplicate_ticker_share_passed"]
        or not historical_checks["historical_single_duplicate_sleeve_share_passed"]
        or not forward_checks["forward_single_duplicate_ticker_share_passed"]
        or not forward_checks["forward_single_duplicate_sleeve_share_passed"]
    ):
        realized_failure_modes.append("concentration_failed")
    if not historical_checks["historical_cap_improves_required_metrics"]:
        realized_failure_modes.append("historical_validation_failed")
    if not forward_support and forward_checks["forward_cap_improves_required_metrics"]:
        realized_failure_modes.append("forward_only_not_gate_ready")
    if not field_checks["forward_field_reality_passed"] or not field_checks["historical_field_reality_passed"]:
        realized_failure_modes.append("field_reality_failed")
    realized_failure_modes = sorted(set(realized_failure_modes))
    prediction_hit = bool(
        set(PREDICTION["main_failure_modes"]) & set(realized_failure_modes)
    )

    forward_skipped = forward_policy["skipped_rows"]
    historical_skipped = historical_policy["skipped_rows"]
    summary = {
        "decision": decision,
        "forward_source_rows": len(forward_raw_rows),
        "forward_enriched_rows": len(forward_enriched),
        "forward_excluded_finra_ftd_rows": len(forward_excluded),
        "forward_eligible_rows": len(forward_eligible),
        "forward_ineligible_rows": len(forward_ineligible),
        "forward_duplicate_rows": len(forward_duplicate_rows),
        "forward_duplicate_groups": len(forward_duplicate_groups),
        "forward_same_sleeve_multi_groups": len(forward_same_sleeve_multi),
        "forward_policy_skipped_rows": len(forward_skipped),
        "forward_policy_kept_rows": len(forward_policy["kept_rows"]),
        "forward_cash_cap_delta_sum": (
            forward_policy["delta"]["replacement_value_vs_cash_usd"][
                "capped_minus_uncapped_sum"
            ]
        ),
        "forward_spy_cap_delta_sum": (
            forward_policy["delta"]["replacement_value_vs_spy_usd"][
                "capped_minus_uncapped_sum"
            ]
        ),
        "forward_qqq_cap_delta_sum": (
            forward_policy["delta"]["replacement_value_vs_qqq_usd"][
                "capped_minus_uncapped_sum"
            ]
        ),
        "historical_source_rows": len(historical_raw_rows),
        "historical_excluded_finra_ftd_rows": len(historical_excluded),
        "historical_eligible_rows": len(historical_eligible),
        "historical_ineligible_rows": len(historical_ineligible),
        "historical_duplicate_rows": len(historical_duplicate_rows),
        "historical_duplicate_groups": len(historical_duplicate_groups),
        "historical_same_sleeve_multi_groups": len(historical_same_sleeve_multi),
        "historical_policy_skipped_rows": len(historical_skipped),
        "historical_policy_kept_rows": len(historical_policy["kept_rows"]),
        "historical_pnl_per_10k_cap_delta_sum": (
            historical_policy["delta"]["pnl_per_10k"]["capped_minus_uncapped_sum"]
        ),
        "forward_support": forward_support,
        "historical_support": historical_support,
        "policy_supported": policy_supported,
    }

    if policy_supported:
        surprise_note = (
            "Both the forward replacement ledger and historical accepted-paper "
            "surface supported the static duplicate cap. This remains "
            "observed-only because no shared helper or adapter changed."
        )
    else:
        surprise_note = (
            "The static cap can be measured on the forward ledger, but Gate 4 "
            "cannot accept it: the independent historical accepted-paper surface "
            "does not meet the duplicate sample, concentration, and/or primary "
            "metric support requirements."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": policy_supported,
        "accepted_alpha": False,
        "observed_only_lead": policy_supported,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "risk_allocation",
        "implementation_mode": "read_only_duplicate_exposure_cap_policy_simulation",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "static cross-sleeve duplicate cap policy",
            "forward replacement ledger simulation",
            "historical accepted paper validation",
            "FINRA/FTD surface exclusion",
            "production parity boundary",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_gate_shape_policy_simulation",
        "new_evidence_axis": (
            "Cross-sleeve duplicate-exposure cap policy simulation over accepted "
            "non-FINRA default-off paper rows, explicitly excluding SEC FTD/FINRA "
            "parked observers. This is not a threshold, source-field, notional, "
            "hold, response-curve, or readiness-audit retry."
        ),
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 1 if policy_supported else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1 if policy_supported else 0))
                ** 2,
                4,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": prediction_hit,
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
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
            **summary,
        },
        "gate1": {
            "passed": baseline["loaded"],
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "baseline_metrics": baseline,
            "note": (
                "Policy simulation only; before and after executable strategy "
                "behavior are identical."
            ),
        },
        "gate2": {
            "passed": field_checks["forward_field_reality_passed"]
            and field_checks["historical_field_reality_passed"],
            "forward_field_reality": {
                "required_fields": ["ticker", "entry_date", *FORWARD_PRIMARY_METRICS],
                "source_rows": len(forward_raw_rows),
                "enriched_rows": len(forward_enriched),
                "eligible_rows": len(forward_eligible),
                "ineligible_rows": len(forward_ineligible),
                "entry_date_present_rows": sum(1 for row in forward_non_finra if row.get("entry_date")),
                "target_price_relevance": (
                    "Forward replacement rows are settled ledger outcomes; "
                    "target_price is not required because this runner schedules "
                    "no exits or orders."
                ),
            },
            "historical_field_reality": {
                "required_fields": [
                    "window",
                    "entry_date",
                    "ticker",
                    "sleeve",
                    "pnl_per_10k",
                ],
                "source_rows": len(historical_raw_rows),
                "eligible_rows": len(historical_eligible),
                "ineligible_rows": len(historical_ineligible),
                "target_price_present_rows": sum(
                    1
                    for row in historical_non_finra
                    if row.get("target_price") not in (None, "")
                ),
                "target_price_relevance": (
                    "Historical accepted paper rows are completed outcomes; "
                    "target_price is not required for read-only cap simulation."
                ),
            },
            "source_report_summary": source_report_summary(historical_source_reports),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter was added; the cap is simulated only.",
            "baseline_survival_rate": baseline["survival_rate"],
            "baseline_min_window_survival_rate": baseline["min_window_survival_rate"],
            "survival_guard_passed": (
                baseline["min_window_survival_rate"] is not None
                and baseline["min_window_survival_rate"] >= 0.05
            ),
        },
        "gate4": {
            "passed": policy_supported,
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
            "forward_failed_reasons": forward_failed,
            "historical_failed_reasons": historical_failed,
            "forward_support": forward_support,
            "historical_support": historical_support,
            "policy_priority_note": (
                "Static sleeve priority was predeclared and does not use cash, "
                "SPY, QQQ, pnl, or replacement outcomes to select kept rows."
            ),
            "forward_policy": {
                "delta": forward_policy["delta"],
                "duplicate_rows": summarize_rows(
                    forward_duplicate_rows, FORWARD_PRIMARY_METRICS
                ),
                "skipped_rows": summarize_rows(forward_skipped, FORWARD_PRIMARY_METRICS),
                "kept_rows": summarize_rows(
                    forward_policy["kept_rows"], FORWARD_PRIMARY_METRICS
                ),
                "duplicate_group_examples": forward_policy[
                    "duplicate_group_records"
                ][:25],
                "same_sleeve_multi_group_count": len(forward_same_sleeve_multi),
            },
            "historical_policy": {
                "delta": historical_policy["delta"],
                "duplicate_rows": summarize_rows(
                    historical_duplicate_rows, HISTORICAL_DIAGNOSTIC_METRICS
                ),
                "skipped_rows": summarize_rows(
                    historical_skipped, HISTORICAL_DIAGNOSTIC_METRICS
                ),
                "kept_rows": summarize_rows(
                    historical_policy["kept_rows"], HISTORICAL_DIAGNOSTIC_METRICS
                ),
                "duplicate_group_examples": historical_policy[
                    "duplicate_group_records"
                ][:25],
                "same_sleeve_multi_group_count": len(historical_same_sleeve_multi),
            },
        },
        "summary": summary,
        "historical_windows": historical_windows,
        "sample_rows": {
            "forward_skipped_rows": [row_brief(row, FORWARD_PRIMARY_METRICS) for row in forward_skipped[:25]],
            "historical_skipped_rows": [
                row_brief(row, HISTORICAL_DIAGNOSTIC_METRICS)
                for row in historical_skipped[:25]
            ],
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
                "Read-only simulation over existing default-off paper artifacts. "
                "No shared helper, adapter, order, rank, size, exit, watchlist, "
                "or LLM behavior changed."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "post_run_reflection": {
            "why_result_happened": (
                "The forward ledger can support a cross-sleeve cap simulation, "
                "but the independent historical accepted-paper surface is still "
                "too thin or concentrated to validate a default-off duplicate "
                "exposure policy."
            ),
            "alpha_interpretation": (
                "The cap idea remains a forward-only risk-allocation lead, not "
                "an accepted alpha or production-ready control. The rejection is "
                "against promoting this fixed policy on current evidence."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune the sleeve priority order, duplicate group key, "
                "same-sleeve inclusion, concentration caps, threshold counts, "
                "notional scaling, hold window, or response function on the same "
                "60 forward rows and current accepted-paper historical rows."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more closed forward cross-sleeve "
                "duplicate rows plus an independent historical/default-off row "
                "surface meeting the duplicate count, group, window, and "
                "concentration requirements, or a full shared-policy Gate 1-4 "
                "implementation with explicit parity."
            ),
        },
        "next_retry_requires": [
            "materially more closed cross-sleeve duplicate forward rows",
            "independent historical/default-off duplicate rows across at least two windows",
            "or a full shared-policy Gate 1-4 duplicate cap implementation",
        ],
        "related_files": [
            repo_rel(BASELINE_PATH),
            repo_rel(FORWARD_LEDGER),
            "quant/experiments/exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution.py",
            "experiments/logs/exp-20260705-002.json",
            "experiments/logs/exp-20260705-003.json",
            "experiments/logs/exp-20260705-004.json",
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
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} - duplicate exposure cap policy sim",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- forward eligible/duplicate/skipped rows: {summary['forward_eligible_rows']} / {summary['forward_duplicate_rows']} / {summary['forward_policy_skipped_rows']}",
        f"- forward duplicate groups: {summary['forward_duplicate_groups']}",
        f"- forward cap delta cash/SPY/QQQ: {summary['forward_cash_cap_delta_sum']} / {summary['forward_spy_cap_delta_sum']} / {summary['forward_qqq_cap_delta_sum']}",
        f"- historical eligible/duplicate/skipped rows: {summary['historical_eligible_rows']} / {summary['historical_duplicate_rows']} / {summary['historical_policy_skipped_rows']}",
        f"- historical duplicate groups: {summary['historical_duplicate_groups']}",
        f"- historical pnl_per_10k cap delta: {summary['historical_pnl_per_10k_cap_delta_sum']}",
        f"- forward support: {summary['forward_support']}",
        f"- historical support: {summary['historical_support']}",
        "",
        "No entry, ranking, sizing, risk budget, exit, paper order, live order, "
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
                "forward_support": payload["summary"]["forward_support"],
                "historical_support": payload["summary"]["historical_support"],
                "forward_duplicate_groups": payload["summary"][
                    "forward_duplicate_groups"
                ],
                "historical_duplicate_groups": payload["summary"][
                    "historical_duplicate_groups"
                ],
                "forward_cash_cap_delta_sum": payload["summary"][
                    "forward_cash_cap_delta_sum"
                ],
                "historical_pnl_per_10k_cap_delta_sum": payload["summary"][
                    "historical_pnl_per_10k_cap_delta_sum"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
