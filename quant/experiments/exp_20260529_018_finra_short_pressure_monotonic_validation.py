"""exp-20260529-018: FINRA short-pressure monotonic validation.

This is a read-only alpha validation. It tests whether the PIT-safe FINRA
short-pressure score used by exp-20260529-017 has durable monotonic ranking
evidence across that experiment's canonical three-window paper trades.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260529-018"
SLUG = "finra_short_pressure_monotonic_validation"
STEM = f"exp_20260529_018_{SLUG}"

SOURCE_EXPERIMENT_ID = "exp-20260529-017"
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260529_017_finra_short_pressure_breakout_candidate_pool.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

CHANGED_VARIABLE = "finra_short_pressure_score_monotonic_bucket_validation_v1"
PRIMARY_SCORE_FIELD = "finra_short_pressure_score"
BUCKET_ORDER = ["top", "middle", "bottom"]
MIN_WINDOWS_WITH_MONOTONIC_AVG = 2
MAX_ALLOWED_TOP_UNDER_BOTTOM_WINDOWS = 0


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    return value


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_trades(source: dict[str, Any]) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    by_window = source.get("target_trades_by_window") or {}
    if not isinstance(by_window, dict):
        raise TypeError("target_trades_by_window missing from source artifact")
    for window in WINDOWS:
        rows = by_window.get(window) or []
        if not isinstance(rows, list):
            raise TypeError(f"target_trades_by_window[{window}] is not a list")
        for row in rows:
            if not isinstance(row, dict):
                continue
            score = _as_float(row.get(PRIMARY_SCORE_FIELD))
            pnl = _as_float(row.get("pnl"))
            if score is None or pnl is None:
                continue
            enriched = dict(row)
            enriched["window"] = window
            enriched[PRIMARY_SCORE_FIELD] = score
            enriched["pnl"] = pnl
            trades.append(enriched)
    return trades


def _split_tertiles(rows: list[dict[str, Any]], score_field: str) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: float(row[score_field]), reverse=True)
    buckets: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in BUCKET_ORDER}
    total = len(ordered)
    if total == 0:
        return buckets
    for index, row in enumerate(ordered):
        rank_fraction = index / total
        if rank_fraction < 1 / 3:
            bucket = "top"
        elif rank_fraction < 2 / 3:
            bucket = "middle"
        else:
            bucket = "bottom"
        buckets[bucket].append(row)
    return buckets


def _bucket_summary(rows: list[dict[str, Any]], score_field: str) -> dict[str, Any]:
    scores = [float(row[score_field]) for row in rows]
    pnls = [float(row["pnl"]) for row in rows]
    tickers = [str(row.get("ticker") or "") for row in rows if row.get("ticker")]
    positives = [pnl for pnl in pnls if pnl > 0]
    positive_by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        pnl = float(row["pnl"])
        if pnl > 0 and row.get("ticker"):
            positive_by_ticker[str(row["ticker"])] += pnl
    positive_total = sum(positive_by_ticker.values())
    max_single_positive_share = (
        max(positive_by_ticker.values()) / positive_total if positive_total > 0 else 0.0
    )
    positive_hhi = (
        sum((value / positive_total) ** 2 for value in positive_by_ticker.values())
        if positive_total > 0
        else 0.0
    )
    return {
        "count": len(rows),
        "unique_tickers": len(set(tickers)),
        "avg_score": _round(sum(scores) / len(scores), 6) if scores else None,
        "min_score": _round(min(scores), 6) if scores else None,
        "max_score": _round(max(scores), 6) if scores else None,
        "total_pnl": _round(sum(pnls), 2) if pnls else 0.0,
        "avg_pnl": _round(sum(pnls) / len(pnls), 2) if pnls else None,
        "median_pnl": _round(median(pnls), 2) if pnls else None,
        "win_rate": _round(len(positives) / len(pnls), 6) if pnls else None,
        "max_single_positive_pnl_share": _round(max_single_positive_share, 6),
        "positive_pnl_hhi": _round(positive_hhi, 6),
        "top_ticker_counts": dict(Counter(tickers).most_common(5)),
    }


def _validate_monotonic(bucket_summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    avg_values = {
        bucket: _as_float(bucket_summaries.get(bucket, {}).get("avg_pnl"))
        for bucket in BUCKET_ORDER
    }
    median_values = {
        bucket: _as_float(bucket_summaries.get(bucket, {}).get("median_pnl"))
        for bucket in BUCKET_ORDER
    }
    counts = {
        bucket: int(bucket_summaries.get(bucket, {}).get("count") or 0)
        for bucket in BUCKET_ORDER
    }
    strict_avg_monotonic = all(value is not None for value in avg_values.values()) and (
        float(avg_values["top"]) > float(avg_values["middle"]) > float(avg_values["bottom"])
    )
    weak_avg_top_over_bottom = (
        avg_values["top"] is not None
        and avg_values["bottom"] is not None
        and float(avg_values["top"]) > float(avg_values["bottom"])
    )
    weak_median_monotonic = all(value is not None for value in median_values.values()) and (
        float(median_values["top"]) >= float(median_values["middle"]) >= float(median_values["bottom"])
    )
    return {
        "counts": counts,
        "avg_pnl_by_bucket": avg_values,
        "median_pnl_by_bucket": median_values,
        "strict_avg_top_middle_bottom": bool(strict_avg_monotonic),
        "weak_avg_top_over_bottom": bool(weak_avg_top_over_bottom),
        "weak_median_top_middle_bottom": bool(weak_median_monotonic),
    }


def _score_validation(scope: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = _split_tertiles(rows, PRIMARY_SCORE_FIELD)
    bucket_summaries = {
        bucket: _bucket_summary(bucket_rows, PRIMARY_SCORE_FIELD)
        for bucket, bucket_rows in buckets.items()
    }
    validation = _validate_monotonic(bucket_summaries)
    return {
        "scope": scope,
        "trade_count": len(rows),
        "bucket_method": "tertiles_sorted_desc_within_scope",
        "score_field": PRIMARY_SCORE_FIELD,
        "bucket_summaries": bucket_summaries,
        "validation": validation,
    }


def _build_validation(trades: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = {
        window: [row for row in trades if row.get("window") == window]
        for window in WINDOWS
    }
    window_results = {
        window: _score_validation(window, rows)
        for window, rows in by_window.items()
    }
    aggregate = _score_validation("aggregate", trades)
    strict_windows = [
        window
        for window, result in window_results.items()
        if result["validation"]["strict_avg_top_middle_bottom"]
    ]
    top_under_bottom_windows = [
        window
        for window, result in window_results.items()
        if not result["validation"]["weak_avg_top_over_bottom"]
    ]
    passed = (
        aggregate["validation"]["strict_avg_top_middle_bottom"]
        and aggregate["validation"]["weak_median_top_middle_bottom"]
        and len(strict_windows) >= MIN_WINDOWS_WITH_MONOTONIC_AVG
        and len(top_under_bottom_windows) <= MAX_ALLOWED_TOP_UNDER_BOTTOM_WINDOWS
    )
    failed_reasons: list[str] = []
    if not aggregate["validation"]["strict_avg_top_middle_bottom"]:
        failed_reasons.append("aggregate_avg_pnl_not_monotonic")
    if not aggregate["validation"]["weak_median_top_middle_bottom"]:
        failed_reasons.append("aggregate_median_pnl_not_monotonic")
    if len(strict_windows) < MIN_WINDOWS_WITH_MONOTONIC_AVG:
        failed_reasons.append("too_few_windows_with_strict_monotonic_avg_pnl")
    if len(top_under_bottom_windows) > MAX_ALLOWED_TOP_UNDER_BOTTOM_WINDOWS:
        failed_reasons.append("at_least_one_window_top_bucket_underperformed_bottom")
    return {
        "aggregate": aggregate,
        "by_window": window_results,
        "strict_monotonic_windows": strict_windows,
        "top_under_bottom_windows": top_under_bottom_windows,
        "passed": passed,
        "failed_reasons": failed_reasons,
        "acceptance_rule": {
            "aggregate_strict_avg_top_middle_bottom_required": True,
            "aggregate_weak_median_top_middle_bottom_required": True,
            "min_windows_with_strict_avg_monotonic": MIN_WINDOWS_WITH_MONOTONIC_AVG,
            "max_allowed_top_under_bottom_windows": MAX_ALLOWED_TOP_UNDER_BOTTOM_WINDOWS,
        },
    }


def _compact_metrics(metrics_by_window: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "survival_rate",
        "signals_generated",
        "signals_survived",
    ]
    compact: dict[str, dict[str, Any]] = {}
    for window in WINDOWS:
        metrics = metrics_by_window.get(window) or {}
        compact[window] = {
            field: _round(metrics.get(field), 6)
            for field in fields
            if isinstance(metrics, dict) and field in metrics
        }
    return compact


def _sum_metric(metrics_by_window: dict[str, Any], field: str) -> float:
    total = 0.0
    for metrics in metrics_by_window.values():
        if isinstance(metrics, dict):
            total += float(metrics.get(field) or 0.0)
    return round(total, 6)


def _build_payload() -> dict[str, Any]:
    source = _load_json(SOURCE_JSON)
    if not isinstance(source, dict):
        raise TypeError(f"Expected source JSON object: {SOURCE_JSON}")
    trades = _extract_trades(source)
    validation = _build_validation(trades)
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    before_metrics = _compact_metrics(source.get("before_metrics") or {})
    after_metrics = _compact_metrics(source.get("after_metrics") or {})
    source_gate4 = source.get("gate4") or {}
    decision = (
        "accepted_finra_short_pressure_monotonic_validation"
        if validation["passed"]
        else "rejected_no_finra_short_pressure_monotonic_edge"
    )
    status = "observed_only" if validation["passed"] else "rejected"
    interpretation = (
        "FINRA short-pressure has stable monotonic ranking evidence on the exp017 "
        "candidate pool."
        if validation["passed"]
        else "FINRA short-pressure does not have stable monotonic ranking evidence; "
        "do not refine it into another threshold, scalar, source, or rank rule without "
        "new forward rows or a materially different production-visible FINRA field."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_discovery",
        "hypothesis": (
            "PIT FINRA short-pressure should show durable monotonic ranking evidence "
            "if it is a real candidate-pool alpha field; top short-pressure buckets "
            "should outperform lower buckets across the canonical three-window "
            "exp-20260529-017 candidate trades."
        ),
        "change_type": "read_only_monotonic_validation",
        "mechanism_family": "finra_short_pressure_candidate_pool",
        "trial_family": "finra_short_pressure_monotonic_validation",
        "trial_variant_id": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260516-035",
            "exp-20260516-037",
            "exp-20260529-017",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "monotonic_validation_on_existing_three_window_candidate_pool",
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_JSON),
            "primary_score_field": PRIMARY_SCORE_FIELD,
            "bucket_method": "tertiles_sorted_desc_within_aggregate_and_each_window",
            "target_trade_count": len(trades),
            "acceptance_rule": validation["acceptance_rule"],
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay via exp-20260529-017",
            "windows": WINDOWS,
            "strategy_behavior_changed": False,
            "replay_llm": False,
            "replay_news": False,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking / candidate-pool validation: a real FINRA short-pressure "
                "alpha field should show monotonic bucket ordering before any "
                "threshold or allocation retry."
            ),
            "2_history_check": (
                "exp-20260516-035 FINRA days-to-cover haircut failed; "
                "exp-20260516-037 FINRA squeeze top-up was immaterial/thin; "
                "exp-20260529-017 FINRA short-pressure breakout source failed "
                "Gate 4 due mid_weak EV/PnL regression."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Read-only monotonic validation using exp017's canonical three-window "
                "trades: aggregate top>middle>bottom by avg PnL, aggregate median "
                "non-increasing from top to bottom, at least two windows strictly "
                "monotonic by avg PnL, and zero windows with top bucket below bottom."
            ),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260529_018_finra_short_pressure_monotonic_validation.py"
            ),
        },
        "gate1": {
            "passed": True,
            "protocol": "docs/backtesting.md canonical three fixed windows",
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "source_gate4_passed": bool(source_gate4.get("passed")),
            "source_gate4_failed_reasons": source_gate4.get("failed_reasons") or [],
            "source_before_metrics": before_metrics,
            "source_after_metrics": after_metrics,
            "windows": WINDOWS,
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                "target_trades_by_window[].finra_short_pressure_score",
                "target_trades_by_window[].pnl",
                "target_trades_by_window[].ticker",
                "target_trades_by_window[].signal_date",
            ],
            "field_coverage": {
                "target_trade_count": len(trades),
                "score_present_count": len([row for row in trades if row.get(PRIMARY_SCORE_FIELD) is not None]),
                "pnl_present_count": len([row for row in trades if row.get("pnl") is not None]),
            },
        },
        "gate3": {
            "passed": True,
            "survival_audit": (
                "No filter, entry, ranking, sizing, exit, or order behavior changed. "
                "Source exp017 core survival stayed >= 79.25%."
            ),
            "source_survival_by_window": {
                window: before_metrics.get(window, {}).get("survival_rate")
                for window in WINDOWS
            },
        },
        "gate4": {
            "passed": validation["passed"],
            "strategy_behavior_changed": False,
            "basis": "Read-only monotonic validation; no executable policy retained.",
            "failed_reasons": validation["failed_reasons"],
            "source_exp017_gate4_passed": bool(source_gate4.get("passed")),
            "source_exp017_gate4_failed_reasons": source_gate4.get("failed_reasons") or [],
            "validation": validation,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "source_exp017": source.get("delta_metrics") or {},
            "monotonic_validation": {
                "passed": validation["passed"],
                "strict_monotonic_windows": validation["strict_monotonic_windows"],
                "top_under_bottom_windows": validation["top_under_bottom_windows"],
                "failed_reasons": validation["failed_reasons"],
            },
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "monotonic_validation": validation,
        "interpretation": interpretation,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": False,
            "read_only_validation": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "next_retry_requires": [
            "New forward closed rows with FINRA short-pressure fields.",
            "A materially different FINRA production-visible field, not another nearby threshold/scalar retry.",
            "Fresh three-window Gate 1-4 evidence before any shared policy or default-off source promotion.",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(SOURCE_JSON),
            "docs/backtesting.md",
            "docs/alpha-optimization-playbook.md",
            "docs/production_backtest_parity.md",
        ],
        "anti_js": "No JavaScript was used.",
        "llm_metrics": {"used_llm": False},
        "notes": (
            "This run intentionally stops at evidence extraction. A failed "
            "monotonic validation means the FINRA short-pressure feature should "
            "not be promoted or retuned on the frozen sample."
        ),
        "source_aggregate": {
            "before_expected_value_score_sum": _sum_metric(source.get("before_metrics") or {}, "expected_value_score"),
            "after_expected_value_score_sum": _sum_metric(source.get("after_metrics") or {}, "expected_value_score"),
            "before_total_pnl_sum": _sum_metric(source.get("before_metrics") or {}, "total_pnl"),
            "after_total_pnl_sum": _sum_metric(source.get("after_metrics") or {}, "total_pnl"),
        },
    }


def _jsonl_has_experiment(path: Path, experiment_id: str) -> bool:
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == experiment_id:
                return True
    return False


def _append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _jsonl_has_experiment(path, str(row["experiment_id"])):
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _record_for_jsonl(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Validated whether exp017 PIT FINRA short-pressure score is monotonic "
            "across canonical three-window paper trade outcomes."
        ),
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "date_range": {"windows": WINDOWS},
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "production_impact": payload["production_impact"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": {
            "passed": payload["gate4"]["passed"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "strategy_behavior_changed": False,
            "source_exp017_gate4_passed": payload["gate4"]["source_exp017_gate4_passed"],
        },
        "monotonic_validation": payload["monotonic_validation"],
        "rejection_reason": None if payload["gate4"]["passed"] else payload["interpretation"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "notes": payload["notes"],
    }


def _build_card(payload: dict[str, Any]) -> str:
    validation = payload["monotonic_validation"]
    aggregate = validation["aggregate"]["bucket_summaries"]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        f'status: "{payload["status"]}"',
        f'lane: "{payload["lane"]}"',
        f'change_type: "{payload["change_type"]}"',
        f'mechanism_family: "{payload["mechanism_family"]}"',
        f'trial_family: "{payload["trial_family"]}"',
        f'trial_variant_id: "{payload["trial_variant_id"]}"',
        f'changed_variable: "{payload["changed_variable"]}"',
        f'new_evidence_type: "{payload["new_evidence_type"]}"',
        f'completed_at: "{payload["timestamp"]}"',
        "tags:",
        '  - "alpha_discovery"',
        '  - "read_only_monotonic_validation"',
        '  - "finra_short_pressure"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Summary",
        "",
        "Read-only monotonic validation of the PIT FINRA short-pressure score on "
        "the exp-20260529-017 candidate-pool paper trades.",
        "",
        "## Gate Questions",
        "",
    ]
    for value in payload["gate_questions"].values():
        lines.append(f"- {value}")
    lines.extend(
        [
            "",
            "## Aggregate Buckets",
            "",
            "| Bucket | Count | Avg score | Avg PnL | Median PnL | Win rate | Total PnL |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for bucket in BUCKET_ORDER:
        row = aggregate[bucket]
        lines.append(
            "| {bucket} | {count} | {avg_score:.4f} | ${avg_pnl:,.2f} | "
            "${median_pnl:,.2f} | {win_rate:.2%} | ${total_pnl:,.2f} |".format(
                bucket=bucket,
                count=row["count"],
                avg_score=float(row["avg_score"] or 0.0),
                avg_pnl=float(row["avg_pnl"] or 0.0),
                median_pnl=float(row["median_pnl"] or 0.0),
                win_rate=float(row["win_rate"] or 0.0),
                total_pnl=float(row["total_pnl"] or 0.0),
            )
        )
    lines.extend(["", "## Window Verdict", ""])
    for window, result in validation["by_window"].items():
        verdict = "pass" if result["validation"]["strict_avg_top_middle_bottom"] else "fail"
        avg = result["validation"]["avg_pnl_by_bucket"]
        lines.append(
            f"- `{window}`: {verdict}; avg PnL top/middle/bottom = "
            f"{avg['top']} / {avg['middle']} / {avg['bottom']}"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Failed reasons: `{', '.join(validation['failed_reasons']) or 'none'}`",
            f"- Interpretation: {payload['interpretation']}",
            "",
            "## Production Impact",
            "",
            "No shared policy, backtester adapter, run adapter, ranking, sizing, exit, "
            "watchlist, LLM/news, or order behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def _update_ticket(payload: dict[str, Any]) -> None:
    if not TICKET_JSON.exists():
        ticket = {"experiment_id": EXPERIMENT_ID}
    else:
        ticket = _load_json(TICKET_JSON)
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "json": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "passed": payload["gate4"]["passed"],
        "failed_reasons": payload["gate4"]["failed_reasons"],
    }
    _write_json(TICKET_JSON, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    if not MANIFEST_JSON.exists():
        manifest = {"experiment_id": EXPERIMENT_ID}
    else:
        manifest = _load_json(MANIFEST_JSON)
    manifest["completed_at"] = payload["timestamp"]
    manifest["result_files"] = {
        "json": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
    }
    _write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments") if isinstance(registry, dict) else None
    if not isinstance(experiments, list):
        return
    for experiment in experiments:
        if isinstance(experiment, dict) and experiment.get("experiment_id") == EXPERIMENT_ID:
            experiment["status"] = payload["status"]
            experiment["completed_at"] = payload["timestamp"]
            experiment["result"] = {
                "decision": payload["decision"],
                "json": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "card": _repo_rel(CARD_MD),
                "passed": payload["gate4"]["passed"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            }
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def main() -> int:
    payload = _build_payload()
    record = _record_for_jsonl(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _append_jsonl_once(EXPERIMENT_LOG, record)
    _update_ticket(payload)
    _update_manifest(payload)
    _update_registry(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "passed": payload["gate4"]["passed"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "json": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "card": _repo_rel(CARD_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
