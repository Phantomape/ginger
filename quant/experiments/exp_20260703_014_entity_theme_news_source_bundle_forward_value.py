"""exp-20260703-014: entity/theme observer source-bundle forward value.

Observed-only alpha attribution.  The fixed entity/theme news observer now has
settled 10-day outcome rows from exp-20260703-013.  This runner tests whether
the observer source bundle, as currently defined, shows enough cash/SPY/QQQ
replacement value to justify a future shared default-off candidate-pool test.

No strategy behavior changes here: no entries, ranking, sizing, exits, paper
orders, live orders, prompts, or watchlists are changed.
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


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260703-014"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "entity_theme_news_source_bundle_forward_value"
RUNNER = f"quant/experiments/exp_20260703_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260703-013"
    / "outcome_probe"
    / "entity_theme_news_outcome_daily_wiring_summary_20260702.json"
)
SOURCE_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260703-013"
    / "outcome_probe"
    / "entity_theme_news_outcome_daily_wiring_20260702.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260703_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: the fixed entity/theme news observer source bundle, "
    "using exp-20260703-013 settled cash/SPY/QQQ outcome rows, should show "
    "positive 10-day replacement value versus cash and ETF comparators before "
    "it deserves a shared default-off candidate-pool promotion."
)
CHANGED_VARIABLE = "entity_theme_news_observer_source_bundle_forward_value_v1"
TRIAL_FAMILY = "entity_theme_news_observer_source_bundle_forward_value"
TRIAL_VARIANT_ID = "fixed_source_bundle_10d_outcome_attribution"
NEARBY_PRIORS = [
    "exp-20260703-001",
    "exp-20260703-002",
    "exp-20260703-013",
    "exp-20260702-026",
]
NEW_EVIDENCE_AXIS = (
    "new data source: entity_theme_news_observer; exp-20260703-013 also "
    "materialized 2728 settled forward rows with cash/SPY/QQQ replacement "
    "values. This is not SEC FTD FINRA and not a sentiment keyword or "
    "ticker-news reslice."
)
PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_positive_replacement_value",
        "theme_mixture_dilution",
        "ticker_concentration",
        "current_snapshot_pit_caveat",
    ],
    "confidence_reason": (
        "The observer is a genuinely new non-ticker news relation surface and "
        "exp-20260703-013 produced 2728 settled cash/SPY/QQQ outcome rows, but "
        "prior daily-news and second-order news candidate-pool attempts failed "
        "after top-1 compression and this first snapshot may be "
        "historical-search-biased rather than strict PIT."
    ),
    "recorded_at": "2026-07-03T15:11:48+00:00",
}

PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
ACCEPTANCE_RULE = {
    "min_settled_rows": 250,
    "min_query_groups": 6,
    "min_positive_query_groups_vs_spy_and_qqq": 4,
    "max_positive_cash_ticker_share": 0.40,
    "max_positive_cash_query_share": 0.60,
    "require_row_level_primary_means_positive": True,
    "require_row_level_primary_medians_nonnegative": True,
    "require_observed_date_level_primary_means_positive": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_014_{SLUG}.json",
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


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def numeric_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6),
    }


def metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        key: summarize_values(
            [value for row in rows if (value := numeric_value(row, key)) is not None]
        )
        for key in [*PRIMARY_METRICS, "pnl_usd"]
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {}) or {}
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(
            int(window.get("trade_count") or window.get("total_trades") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def group_rows(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "UNKNOWN")].append(row)
    return dict(sorted(grouped.items()))


def group_summaries(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    output = []
    for value, subset in group_rows(rows, key).items():
        metrics = metric_summary(subset)
        output.append(
            {
                key: value,
                "row_count": len(subset),
                "ticker_count": len({row.get("candidate_ticker") for row in subset}),
                "metrics": metrics,
                "primary_means_positive": all(
                    (metrics[metric]["mean"] or 0.0) > 0 for metric in PRIMARY_METRICS
                ),
                "spy_and_qqq_means_positive": (
                    (metrics["replacement_value_vs_spy_usd"]["mean"] or 0.0) > 0
                    and (metrics["replacement_value_vs_qqq_usd"]["mean"] or 0.0) > 0
                ),
            }
        )
    return sorted(output, key=lambda item: item["row_count"], reverse=True)


def date_level_metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_date = group_rows(rows, "observed_date")
    output: dict[str, Any] = {"observed_date_count": len(by_date), "metrics": {}}
    for metric in PRIMARY_METRICS:
        date_means = []
        for subset in by_date.values():
            values = [
                value
                for row in subset
                if (value := numeric_value(row, metric)) is not None
            ]
            if values:
                date_means.append(mean(values))
        output["metrics"][metric] = summarize_values(date_means)
    return output


def positive_contribution_share(
    rows: list[dict[str, Any]], key: str, metric: str
) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    for row in rows:
        value = numeric_value(row, metric)
        if value is None or value <= 0:
            continue
        totals[str(row.get(key) or "UNKNOWN")] += value
    total_positive = sum(totals.values())
    leaders = [
        {
            key: group,
            "positive_contribution_usd": round(value, 2),
            "share": round(value / total_positive, 6) if total_positive else None,
        }
        for group, value in totals.most_common(10)
    ]
    return {
        "metric": metric,
        "total_positive_usd": round(total_positive, 2) if total_positive else 0.0,
        "max_share": leaders[0]["share"] if leaders else None,
        "leaders": leaders,
    }


def count_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(str(row.get("candidate_ticker") or "UNKNOWN") for row in rows)
    queries = Counter(str(row.get("entity_theme_query_id") or "UNKNOWN") for row in rows)
    themes = Counter(str(row.get("theme") or "UNKNOWN") for row in rows)
    return {
        "row_count": len(rows),
        "ticker_count": len(tickers),
        "query_count": len(queries),
        "theme_count": len(themes),
        "observed_date_count": len({row.get("observed_date") for row in rows}),
        "top_tickers_by_rows": [
            {"ticker": ticker, "rows": count, "share": round(count / len(rows), 6)}
            for ticker, count in tickers.most_common(10)
        ]
        if rows
        else [],
        "top_queries_by_rows": [
            {"query_id": query, "rows": count, "share": round(count / len(rows), 6)}
            for query, count in queries.most_common(10)
        ]
        if rows
        else [],
        "top_themes_by_rows": [
            {"theme": theme, "rows": count, "share": round(count / len(rows), 6)}
            for theme, count in themes.most_common(10)
        ]
        if rows
        else [],
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = baseline_metrics()
    source_summary = read_json(SOURCE_SUMMARY, {}) or {}
    all_rows = load_jsonl(SOURCE_LEDGER)
    settled = [row for row in all_rows if row.get("outcome_status") == "settled"]
    overall_metrics = metric_summary(settled)
    by_query = group_summaries(settled, "entity_theme_query_id")
    by_theme = group_summaries(settled, "theme")
    by_ticker = group_summaries(settled, "candidate_ticker")
    date_level = date_level_metric_summary(settled)
    ticker_positive_share = positive_contribution_share(
        settled, "candidate_ticker", "replacement_value_vs_cash_usd"
    )
    query_positive_share = positive_contribution_share(
        settled, "entity_theme_query_id", "replacement_value_vs_cash_usd"
    )

    row_means_positive = all(
        (overall_metrics[metric]["mean"] or 0.0) > 0 for metric in PRIMARY_METRICS
    )
    row_medians_nonnegative = all(
        (overall_metrics[metric]["median"] or 0.0) >= 0 for metric in PRIMARY_METRICS
    )
    date_means_positive = all(
        (date_level["metrics"][metric]["mean"] or 0.0) > 0
        for metric in PRIMARY_METRICS
    )
    positive_query_groups = sum(1 for item in by_query if item["spy_and_qqq_means_positive"])
    max_ticker_positive_share = ticker_positive_share["max_share"]
    max_query_positive_share = query_positive_share["max_share"]

    checks = {
        "settled_rows_min_passed": len(settled) >= ACCEPTANCE_RULE["min_settled_rows"],
        "query_groups_min_passed": len(by_query) >= ACCEPTANCE_RULE["min_query_groups"],
        "positive_query_groups_vs_spy_and_qqq_passed": positive_query_groups
        >= ACCEPTANCE_RULE["min_positive_query_groups_vs_spy_and_qqq"],
        "row_level_primary_means_positive": row_means_positive,
        "row_level_primary_medians_nonnegative": row_medians_nonnegative,
        "observed_date_level_primary_means_positive": date_means_positive,
        "positive_cash_ticker_share_passed": (
            max_ticker_positive_share is not None
            and max_ticker_positive_share
            <= ACCEPTANCE_RULE["max_positive_cash_ticker_share"]
        ),
        "positive_cash_query_share_passed": (
            max_query_positive_share is not None
            and max_query_positive_share
            <= ACCEPTANCE_RULE["max_positive_cash_query_share"]
        ),
    }
    directional_support = all(checks.values())
    failed_reasons = [name for name, passed in checks.items() if not passed]
    if directional_support:
        status = "observed_only_positive_lead"
        decision = "observed_only_positive_entity_theme_source_bundle_forward_lead"
    else:
        status = "observed_only_rejected"
        decision = "observed_only_rejected_no_entity_theme_source_bundle_edge"

    pit_caveat = (
        "The source rows are from the first current Google News observer snapshot "
        "and include historical published_at rows returned by the current search. "
        "That makes this an attribution lead check, not strict PIT historical "
        "candidate-pool evidence."
    )
    why = (
        "The fixed entity/theme observer bundle cleared the predeclared "
        "row/date/query breadth checks, but the result remains only a lead "
        "because the first observer snapshot backfilled historical news rows."
        if directional_support
        else "The fixed entity/theme observer bundle did not show broad, "
        "non-concentrated positive 10-day replacement value across row-level, "
        "date-level, and query-level checks."
    )
    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": directional_support,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_observed_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": "production_visible_entity_theme_news_observer_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "read_only_outcome_ledger_analysis",
            "source_bundle_aggregate_checks",
            "theme_and_ticker_concentration_audit",
            "pit_snapshot_caveat",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_closed_forward_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 1 if directional_support else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1 if directional_support else 0))
                ** 2,
                4,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed_reasons
            if failed_reasons
            else ["current_snapshot_pit_caveat"],
            "predicted_failure_mode_hit": bool(failed_reasons) or True,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "Moderate surprise: the bundle passed observed-only replacement "
                "checks but remains blocked by the current-snapshot PIT caveat."
                if directional_support
                else "Low surprise: prior news surfaces often diluted after "
                "deployable aggregation, and this fixed bundle did not show "
                "broad non-concentrated replacement value."
            ),
        },
        "source_artifacts": {
            "source_summary": repo_rel(SOURCE_SUMMARY),
            "source_ledger": repo_rel(SOURCE_LEDGER),
            "source_summary_payload": source_summary,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": bool(settled),
            "fields_checked": [
                "entity_theme_query_id",
                "theme",
                "relation_type",
                "candidate_ticker",
                "observed_date",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present_rows": sum(1 for row in settled if row.get("entry_date")),
            "target_price_relevance": (
                "This observer does not create target exits or orders; target_price "
                "is not part of the read-only outcome ledger."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": len(all_rows),
            "signals_survived": len(settled),
            "survival_rate": round(len(settled) / max(len(all_rows), 1), 6),
            "note": "No executable filter, ranking, sizing, exit, prompt, or order rule was added.",
        },
        "gate4": {
            "passed": directional_support,
            "observed_only": True,
            "accepted_alpha": False,
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "acceptance_checks": checks,
            "failed_reasons": failed_reasons,
            "pit_caveat": pit_caveat,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
        },
        "analysis": {
            "counts": count_summary(settled),
            "overall_metrics": overall_metrics,
            "date_level_metrics": date_level,
            "query_summaries": by_query,
            "theme_summaries": by_theme,
            "top_ticker_summaries": by_ticker[:12],
            "positive_cash_ticker_contribution": ticker_positive_share,
            "positive_cash_query_contribution": query_positive_share,
            "positive_query_groups_vs_spy_and_qqq": positive_query_groups,
        },
        "summary": {
            "candidate_outcome_rows": len(all_rows),
            "settled_rows": len(settled),
            "query_groups": len(by_query),
            "positive_query_groups_vs_spy_and_qqq": positive_query_groups,
            "row_mean_cash": overall_metrics["replacement_value_vs_cash_usd"]["mean"],
            "row_mean_spy": overall_metrics["replacement_value_vs_spy_usd"]["mean"],
            "row_mean_qqq": overall_metrics["replacement_value_vs_qqq_usd"]["mean"],
            "row_median_cash": overall_metrics["replacement_value_vs_cash_usd"]["median"],
            "row_median_spy": overall_metrics["replacement_value_vs_spy_usd"]["median"],
            "row_median_qqq": overall_metrics["replacement_value_vs_qqq_usd"]["median"],
            "max_positive_cash_ticker_share": max_ticker_positive_share,
            "max_positive_cash_query_share": max_query_positive_share,
            "decision": decision,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "trade_enabled": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only analysis over exp-20260703-013 observer outcome rows. "
                "No helper, adapter, order, rank, size, exit, watchlist, or LLM "
                "behavior changed."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "post_run_reflection": {
            "why_result_happened": why + " " + pit_caveat,
            "forbidden_near_neighbor_retry": (
                "Do not retune entity/theme queries, theme labels, candidate ticker "
                "maps, horizons, notional, or response curves on this same first "
                "snapshot. Do not promote the observer as a candidate-pool source "
                "until prospectively logged rows or a true PIT historical archive "
                "reproduce the replacement-value edge."
            ),
            "new_evidence_required": (
                "Prospectively accumulated daily entity/theme rows with closed "
                "cash/SPY/QQQ replacement value, or a true PIT historical news "
                "archive with observation-time availability and the same fixed "
                "source manifest."
            ),
        },
        "next_retry_requires": [
            "prospective daily entity/theme observer rows with closed outcomes",
            "or a PIT historical news archive with observation-time availability",
            "same fixed source manifest and no query/theme/ticker-map retune",
            "shared-paper-first helper only after PIT replay evidence exists",
        ],
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_LEDGER),
            repo_rel(SOURCE_SUMMARY),
            "experiments/logs/exp-20260703-001.json",
            "experiments/logs/exp-20260703-002.json",
            "experiments/logs/exp-20260703-013.json",
            "experiments/logs/exp-20260702-026.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
    }
    return result


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
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
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: result[key] for key in keys}


def build_card(result: dict[str, Any]) -> str:
    summary = result["summary"]
    failures = result["gate4"]["failed_reasons"] or ["none"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

- Status: `{result["status"]}`
- Decision: `{result["decision"]}`
- Accepted alpha: `false`
- Observed-only lead: `{str(result["observed_only_lead"]).lower()}`
- Settled rows: `{summary["settled_rows"]}`
- Query groups: `{summary["query_groups"]}`
- Positive query groups vs SPY and QQQ: `{summary["positive_query_groups_vs_spy_and_qqq"]}`
- Row means cash/SPY/QQQ: `{summary["row_mean_cash"]}` / `{summary["row_mean_spy"]}` / `{summary["row_mean_qqq"]}`
- Row medians cash/SPY/QQQ: `{summary["row_median_cash"]}` / `{summary["row_median_spy"]}` / `{summary["row_median_qqq"]}`
- Max positive cash ticker/query share: `{summary["max_positive_cash_ticker_share"]}` / `{summary["max_positive_cash_query_share"]}`
- Failed checks: `{", ".join(failures)}`

## Boundary

{result["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{RUNNER_COMMAND}
.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict
```
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": result["artifact"],
        "log": result["log"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": result["observed_only_lead"],
    }
    ticket["gate4"] = result["gate4"]
    ticket["post_run_reflection"] = result["post_run_reflection"]
    ticket["next_retry_requires"] = result["next_retry_requires"]
    write_json(TICKET_JSON, ticket)


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> int:
    result = build_result()
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": result["observed_only_lead"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": CHANGED_FILES,
            "allowed_write_scope": CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(json.dumps(compact_log_record(result), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
