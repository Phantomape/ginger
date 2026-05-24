"""exp-20260524-028: core alpha-score monotonicity audit.

Alpha search, observed-only. This tests whether the existing point-in-time
cross-sectional alpha_score is monotonic enough to justify future allocation
work. It adds no feature and changes no strategy behavior.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260522_025_core_downside_path_haircut as base
from entry_day_ranking_attribution import (
    RANK_BUCKET_ORDER,
    build_entry_day_ranking_attribution,
    load_ohlcv_snapshot,
)


EXPERIMENT_ID = "exp-20260524-028"
STEM = "core_alpha_score_monotonicity_audit"
MECHANISM_FAMILY = "core_cross_sectional_ranking_validation"
TRIAL_FAMILY = "core_alpha_score_monotonicity_audit"
CHANGED_VARIABLE = "none_observed_only_alpha_score_bucket_validation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = base.WINDOWS
ORDERED_BUCKETS = [
    "top_decile",
    "top_quartile",
    "upper_mid",
    "lower_mid",
    "bottom_quartile",
]
MIN_PIT_COVERAGE = 0.95
MIN_NONEMPTY_BUCKETS = 3


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), sort_keys=True, ensure_ascii=True)
    kept: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                kept.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    kept.append(line)
                    replaced = True
                continue
            kept.append(existing)
    if not replaced:
        kept.append(line)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _run_window(label: str, window: dict[str, Any]) -> dict[str, Any]:
    engine = base.BacktestEngine(
        sorted(base.get_universe()),
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    )
    return engine.run()


def _pnl(row: dict[str, Any]) -> float | None:
    try:
        return float(row.get("pnl"))
    except (TypeError, ValueError):
        return None


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [pnl for pnl in (_pnl(row) for row in rows) if pnl is not None]
    wins = sum(1 for pnl in values if pnl > 0)
    return {
        "trades": len(values),
        "win_rate": round(wins / len(values), 4) if values else None,
        "total_pnl": round(sum(values), 2) if values else 0.0,
        "avg_pnl": round(sum(values) / len(values), 2) if values else None,
    }


def _bucket_summary(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in ORDERED_BUCKETS}
    buckets["unknown"] = []
    for trade in trades:
        bucket = str(trade.get("alpha_score_bucket") or "unknown")
        buckets.setdefault(bucket, []).append(trade)
    return [
        {"bucket": bucket, **_summary(rows)}
        for bucket, rows in sorted(
            buckets.items(),
            key=lambda item: RANK_BUCKET_ORDER.get(item[0], 99),
        )
        if rows
    ]


def _combined_summary(trades: list[dict[str, Any]], buckets: set[str]) -> dict[str, Any]:
    return _summary([row for row in trades if row.get("alpha_score_bucket") in buckets])


def _monotonic_check(bucket_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = [
        row
        for row in bucket_rows
        if row["bucket"] in ORDERED_BUCKETS and row["avg_pnl"] is not None
    ]
    nonempty = len(ordered)
    adjacent_pairs = []
    violations = []
    for left, right in zip(ordered, ordered[1:]):
        ok = float(left["avg_pnl"]) >= float(right["avg_pnl"])
        adjacent_pairs.append(
            {
                "higher_bucket": left["bucket"],
                "lower_bucket": right["bucket"],
                "higher_avg_pnl": left["avg_pnl"],
                "lower_avg_pnl": right["avg_pnl"],
                "passed": ok,
            }
        )
        if not ok:
            violations.append(adjacent_pairs[-1])
    return {
        "passed": bool(nonempty >= MIN_NONEMPTY_BUCKETS and not violations),
        "nonempty_rank_buckets": nonempty,
        "minimum_nonempty_rank_buckets": MIN_NONEMPTY_BUCKETS,
        "adjacent_pairs": adjacent_pairs,
        "violations": violations,
    }


def _aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return base.core_helper._aggregate(metrics)


def _artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Core Alpha-Score Monotonicity Audit",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Observed-only alpha search: no entries, exits, ranking, sizing, LLM/news, or orders changed.",
        "",
        "## Three-Window Metrics",
        "",
        "| Window | EV | PnL | Trades | PIT Coverage | Alpha Coverage |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        metrics = payload["before_metrics"]["windows"][label]
        coverage = payload["ranking_attribution"][label]["coverage"]
        lines.append(
            "| {label} | {ev:.4f} | ${pnl:,.2f} | {trades} | {pit:.2%} | {alpha:.2%} |".format(
                label=label,
                ev=float(metrics["expected_value_score"]),
                pnl=float(metrics["total_pnl"]),
                trades=int(metrics["trade_count"]),
                pit=float(coverage["point_in_time_safe_coverage"]),
                alpha=(
                    float(coverage["trades_with_alpha_score"])
                    / float(coverage["trades_total"])
                    if coverage["trades_total"]
                    else 0.0
                ),
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate Bucket Evidence",
            "",
            "| Bucket | Trades | Win Rate | Total PnL | Avg PnL |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload["aggregate_bucket_summary"]:
        lines.append(
            "| {bucket} | {trades} | {win_rate} | ${total:,.2f} | ${avg:,.2f} |".format(
                bucket=row["bucket"],
                trades=row["trades"],
                win_rate="" if row["win_rate"] is None else f"{row['win_rate']:.2%}",
                total=float(row["total_pnl"]),
                avg=float(row["avg_pnl"]) if row["avg_pnl"] is not None else 0.0,
            )
        )
    lines.extend(
        [
            "",
            "## Monotonic Gate",
            "",
            "```json",
            json.dumps(payload["monotonic_gate"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    field_check = base._open_position_field_check()
    results = OrderedDict((label, _run_window(label, window)) for label, window in WINDOWS.items())
    before_metrics = OrderedDict(
        (label, base.core_helper._metrics(result)) for label, result in results.items()
    )

    ranking_attribution: OrderedDict[str, dict[str, Any]] = OrderedDict()
    all_annotated: list[dict[str, Any]] = []
    for label, window in WINDOWS.items():
        ohlcv = load_ohlcv_snapshot(REPO_ROOT / window["snapshot"])
        report = build_entry_day_ranking_attribution(
            result=results[label],
            ohlcv=ohlcv,
            include_annotated_trades=True,
        )
        ranking_attribution[label] = report
        for trade in report.get("annotated_trades", []):
            all_annotated.append({**trade, "window": label})

    aggregate_bucket_summary = _bucket_summary(all_annotated)
    top_rank = _combined_summary(all_annotated, {"top_decile", "top_quartile"})
    lower_rank = _combined_summary(
        all_annotated,
        {"upper_mid", "lower_mid", "bottom_quartile"},
    )
    monotonic = _monotonic_check(aggregate_bucket_summary)
    coverage_passed = all(
        row["coverage"]["point_in_time_safe_coverage"] >= MIN_PIT_COVERAGE
        for row in ranking_attribution.values()
    )
    top_vs_lower_passed = (
        top_rank["trades"] > 0
        and lower_rank["trades"] > 0
        and top_rank["avg_pnl"] is not None
        and lower_rank["avg_pnl"] is not None
        and float(top_rank["avg_pnl"]) > float(lower_rank["avg_pnl"])
    )
    monotonic_gate = {
        "passed": bool(monotonic["passed"] and coverage_passed and top_vs_lower_passed),
        "rank_bucket_monotonicity": monotonic,
        "coverage_passed": coverage_passed,
        "minimum_point_in_time_coverage": MIN_PIT_COVERAGE,
        "top_rank_summary": top_rank,
        "lower_rank_summary": lower_rank,
        "top_rank_outperformed_lower_rank": top_vs_lower_passed,
    }
    decision = (
        "observed_only_promising_alpha_score_monotonicity"
        if monotonic_gate["passed"]
        else "rejected_raw_alpha_score_monotonicity"
    )
    aggregate_metrics = _aggregate(before_metrics)
    gate3 = {
        "adds_filter": False,
        "signals_generated_sum": aggregate_metrics["signals_generated_sum"],
        "signals_survived_sum": aggregate_metrics["signals_survived_sum"],
        "survival_rate_min": aggregate_metrics["survival_rate_min"],
        "passed": aggregate_metrics["survival_rate_min"] >= 0.05,
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "observed_only" if monotonic_gate["passed"] else "rejected",
        "decision": decision,
        "hypothesis": (
            "If Ginger should evolve toward continuous cross-sectional ranking, "
            "the existing point-in-time alpha_score must show stable monotonic "
            "trade outcome evidence across the canonical windows before it is "
            "used for allocation or ranking."
        ),
        "change_summary": (
            "Observed-only PIT entry-day alpha_score bucket attribution across "
            "the canonical three windows; no strategy behavior changed."
        ),
        "change_type": "observed_only_ranking_validation",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "alpha_score_bucket_monotonicity",
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 6,
        "nearby_prior_experiments": [
            "exp-20260524-003",
            "exp-20260524-007",
            "exp-20260524-011",
            "exp-20260524-012",
            "exp-20260524-013",
            "exp-20260524-018",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "monotonic_validation_of_existing_pit_ranking_surface",
        "component": "quant/entry_day_ranking_attribution.py",
        "parameters": {
            "rank_buckets": ORDERED_BUCKETS,
            "minimum_point_in_time_coverage": MIN_PIT_COVERAGE,
            "minimum_nonempty_rank_buckets": MIN_NONEMPTY_BUCKETS,
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            "protocol": "docs/backtesting.md standard_three_window",
            "windows": {
                label: {
                    "start": window["start"],
                    "end": window["end"],
                    "snapshot": window["snapshot"],
                    "state_note": window["state_note"],
                }
                for label, window in WINDOWS.items()
            },
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_metrics_readable": True,
            "before_aggregate": aggregate_metrics,
            "artifact": _repo_rel(OUT_JSON),
        },
        "gate2": {
            "passed": field_check.get("missing_count", 0) == 0,
            "field_check": field_check,
            "rule_dependencies": [
                "entry_date in backtest trades",
                "OHLCV snapshot through previous trading day before entry",
                "entry_day_ranking_attribution alpha_score_bucket",
            ],
        },
        "gate3": gate3,
        "gate4": {
            "strategy_behavior_changed": False,
            "before_after_metrics_identical": True,
            "monotonic_gate_passed": monotonic_gate["passed"],
            "passed": False,
            "note": "Observed-only validation; no promotion without a separate shared-policy Gate 1-4 experiment.",
        },
        "before_metrics": {
            "windows": before_metrics,
            "aggregate": aggregate_metrics,
        },
        "after_metrics": {
            "windows": before_metrics,
            "aggregate": aggregate_metrics,
        },
        "delta_metrics": {
            "windows": {
                label: {key: 0 for key in before_metrics[label].keys()}
                for label in WINDOWS
            },
            "aggregate": {key: 0 for key in aggregate_metrics.keys()},
        },
        "ranking_attribution": ranking_attribution,
        "aggregate_bucket_summary": aggregate_bucket_summary,
        "monotonic_gate": monotonic_gate,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "default_off_paper_only": False,
            "parity_test_added": False,
            "live_order_path_changed": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "ranking: existing alpha_score should be monotonic before it can become allocation/ranking policy.",
            "2_history_check": "Recent raw component and interaction top-ups failed or were underpowered; exp-20260524-012 repaired component attribution, enabling this monotonic validation.",
            "3_single_variable": "No strategy variable changed; the single research variable is alpha_score_bucket as an observed ranking discriminator.",
            "4_acceptance": "Observed-only promotion requires PIT coverage >=95%, at least three non-empty ordered buckets, top-ranked buckets outperforming lower buckets, and no adjacent monotonic violations.",
            "5_reproducibility": ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260524_028_core_alpha_score_monotonicity_audit.py",
        },
        "interpretation": (
            "Raw alpha_score should not be promoted directly unless bucket "
            "outcomes are monotonic. This audit is evidence extraction only."
        ),
        "rejection_reason": None
        if monotonic_gate["passed"]
        else "Point-in-time alpha_score bucket outcomes were not sufficiently monotonic for direct allocation/ranking promotion.",
        "next_evidence_needed": (
            "Use component-level or vector-level attribution to find a more durable "
            "leadership/expectation/theme interaction; do not promote raw alpha_score "
            "without new forward rows or stronger monotonic evidence."
        ),
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG_JSONL),
        },
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact = dict(payload)
    compact["ranking_attribution"] = {
        label: {
            "coverage": row["coverage"],
            "ranking_bucket_attribution": row["ranking_bucket_attribution"],
            "component_attribution": row["component_attribution"],
            "leadership_vector_attribution": row["leadership_vector_attribution"],
            "risk_heat_vector_attribution": row["risk_heat_vector_attribution"],
        }
        for label, row in payload["ranking_attribution"].items()
    }
    return compact


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": payload["lane"],
            "status": payload["status"],
            "decision": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "monotonic_gate": payload["monotonic_gate"],
            "production_impact": payload["production_impact"],
            "related_files": payload["related_files"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _log_payload(payload))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "monotonic_gate": payload["monotonic_gate"],
                    "aggregate_ev": payload["before_metrics"]["aggregate"][
                        "expected_value_score_sum"
                    ],
                    "output": payload["related_files"]["output"],
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
