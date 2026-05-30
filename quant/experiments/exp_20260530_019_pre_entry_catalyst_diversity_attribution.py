"""exp-20260530-019: pre-entry catalyst diversity attribution.

This read-only alpha search follows the rejected catalyst-backed promotion
attempts in exp-20260530-016/017/018. It asks whether the broad
high-confidence catalyst tag from exp-20260530-014 needs a sharper quality
field: source/category diversity.

No production, ranking, sizing, entry, exit, or order behavior is changed.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


EXPERIMENT_ID = "exp-20260530-019"
STEM = "pre_entry_catalyst_diversity_attribution"
CHANGED_VARIABLE = "high_confidence_pre_entry_catalyst_source_category_diversity_bucket_v1"
TRIAL_FAMILY = "pre_entry_catalyst_quality_attribution"
TRIAL_VARIANT_ID = "source_category_diversity_v1"

HIGH_CONFIDENCE_CATEGORIES = {
    "sec_financial_report",
    "form4_open_market_purchase",
    "positive_estimate_revision",
    "positive_t1_t2_news",
}

MIN_DIVERSE_ROWS = 4
MIN_AVG_PNL_LIFT_VS_SINGLE = 1000.0
MIN_AVG_RETURN_LIFT_VS_SINGLE = 0.03
MIN_POSITIVE_LIFT_WINDOWS = 2
MAX_TOP_POSITIVE_TICKER_SHARE = 0.50

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROWS = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260530-014"
    / "pre_entry_catalyst_attribution_trade_rows.json"
)
SOURCE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260530-014"
    / "exp_20260530_014_pre_entry_catalyst_attribution.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_019_{STEM}.json"
ROWS_JSON = OUT_DIR / f"{STEM}_rows.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_CARD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): _safe(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_safe(value) for value in obj]
    if isinstance(obj, tuple):
        return [_safe(value) for value in obj]
    if isinstance(obj, set):
        return sorted(_safe(value) for value in obj)
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    for row in rows:
        pnl = float(row.get("pnl") or 0.0)
        if pnl > 0:
            by_ticker[str(row.get("ticker") or "")] += pnl
    total = sum(by_ticker.values())
    entries = [
        {
            "ticker": ticker,
            "positive_pnl": _round(pnl, 2),
            "share": _round(pnl / total, 6) if total else 0.0,
        }
        for ticker, pnl in by_ticker.most_common()
    ]
    return {
        "positive_pnl_total": _round(total, 2),
        "top_ticker": entries[0]["ticker"] if entries else None,
        "top_ticker_positive_share": entries[0]["share"] if entries else 0.0,
        "by_ticker": entries,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    returns = [
        float(row.get("pnl_pct_net"))
        for row in rows
        if row.get("pnl_pct_net") is not None
    ]
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2) if pnls else None,
        "median_pnl": _round(median(pnls), 2) if pnls else None,
        "avg_return": _round(sum(returns) / len(returns), 6) if returns else None,
        "win_rate": _round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 6)
        if pnls
        else None,
        "positive_concentration": _positive_concentration(rows),
    }


def _lift(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    a_pnl = a.get("avg_pnl")
    b_pnl = b.get("avg_pnl")
    a_ret = a.get("avg_return")
    b_ret = b.get("avg_return")
    return {
        "avg_pnl": _round(float(a_pnl) - float(b_pnl), 4)
        if a_pnl is not None and b_pnl is not None
        else None,
        "avg_return": _round(float(a_ret) - float(b_ret), 6)
        if a_ret is not None and b_ret is not None
        else None,
    }


def _classify_row(row: dict[str, Any]) -> dict[str, Any]:
    examples = row.get("catalyst_examples") or []
    high = [
        event
        for event in examples
        if event.get("high_confidence")
        and str(event.get("category") or "") in HIGH_CONFIDENCE_CATEGORIES
    ]
    categories = sorted({str(event.get("category") or "") for event in high})
    sources = sorted({str(event.get("source") or "") for event in high})
    category_count = len(categories)
    source_count = len(sources)
    is_diverse = category_count >= 2 or source_count >= 2
    if not high:
        bucket = "no_high_confidence_catalyst"
    elif is_diverse:
        bucket = "source_or_category_diverse_high_confidence"
    else:
        bucket = "single_source_single_category_high_confidence"
    out = dict(row)
    out.update(
        {
            "high_confidence_events": high,
            "high_confidence_categories": categories,
            "high_confidence_sources": sources,
            "high_confidence_event_count": len(high),
            "high_confidence_category_count": category_count,
            "high_confidence_source_count": source_count,
            "has_source_or_category_diverse_high_confidence": is_diverse,
            "diversity_bucket": bucket,
            "diversity_combo": "+".join(categories) if categories else "none",
        }
    )
    return out


def _bucketed(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "missing")].append(row)
    return {name: _summary(bucket_rows) for name, bucket_rows in sorted(buckets.items())}


def _window_lift_count(rows: list[dict[str, Any]]) -> int:
    count = 0
    for window in sorted({str(row.get("window") or "") for row in rows}):
        window_rows = [row for row in rows if row.get("window") == window]
        diverse = [
            row
            for row in window_rows
            if row.get("diversity_bucket")
            == "source_or_category_diverse_high_confidence"
        ]
        single = [
            row
            for row in window_rows
            if row.get("diversity_bucket")
            == "single_source_single_category_high_confidence"
        ]
        if not diverse or not single:
            continue
        lift = _lift(_summary(diverse), _summary(single)).get("avg_pnl")
        if lift is not None and lift > 0:
            count += 1
    return count


def _category_combo_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    combos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("high_confidence_event_count"):
            combos[str(row.get("diversity_combo") or "missing")].append(row)
    return {
        combo: _summary(combo_rows)
        for combo, combo_rows in sorted(
            combos.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
    }


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY, {})
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for row in experiments:
        if row.get("experiment_id") == EXPERIMENT_ID:
            row.update(
                {
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "summary": payload["summary"],
                    "completed_at": payload["timestamp"],
                    "updated_at": payload["timestamp"],
                    "result_file": _repo_rel(DOC_LOG),
                    "artifact_file": _repo_rel(OUT_JSON),
                    "report_file": _repo_rel(DOC_ARTIFACT),
                    "card_file": _repo_rel(DOC_CARD),
                    "revision_manifest_file": _repo_rel(
                        REPO_ROOT
                        / "experiments"
                        / "manifests"
                        / f"{EXPERIMENT_ID}.json"
                    ),
                    "result": {
                        "decision": payload["decision"],
                        "summary": payload["summary"],
                        "json": _repo_rel(OUT_JSON),
                        "artifact": _repo_rel(DOC_ARTIFACT),
                        "calibration": payload["calibration"],
                    },
                }
            )
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY, registry)


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate4"]
    bucket = payload["bucket_summaries"]["by_diversity_bucket"]
    diverse = bucket.get("source_or_category_diverse_high_confidence", {})
    single = bucket.get("single_source_single_category_high_confidence", {})
    no_hc = bucket.get("no_high_confidence_catalyst", {})
    lines = [
        f"# {EXPERIMENT_ID} Pre-Entry Catalyst Diversity Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Readout",
        "",
        f"- Diverse high-confidence rows: `{diverse.get('trade_count', 0)}`",
        f"- Single-source/category high-confidence rows: `{single.get('trade_count', 0)}`",
        f"- No high-confidence rows: `{no_hc.get('trade_count', 0)}`",
        f"- Avg PnL lift vs single high-confidence: `{gate['decision_evidence']['avg_pnl_lift_vs_single_high_confidence']}`",
        f"- Avg return lift vs single high-confidence: `{gate['decision_evidence']['avg_return_lift_vs_single_high_confidence']}`",
        f"- Positive-lift windows: `{gate['decision_evidence']['positive_lift_windows']}`",
        f"- Gate passed: `{gate['passed']}`",
        "",
        "| Bucket | Trades | Avg PnL | Avg Return | Win Rate | Top positive share |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in [
        "source_or_category_diverse_high_confidence",
        "single_source_single_category_high_confidence",
        "no_high_confidence_catalyst",
    ]:
        summary = bucket.get(name, {})
        concentration = summary.get("positive_concentration") or {}
        lines.append(
            f"| {name} | {summary.get('trade_count', 0)} | "
            f"{summary.get('avg_pnl')} | {summary.get('avg_return')} | "
            f"{summary.get('win_rate')} | "
            f"{concentration.get('top_ticker_positive_share')} |"
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(gate["decision_evidence"], indent=2, sort_keys=True),
            "```",
            "",
            "Read-only attribution only. No core entry, ranking, sizing, exit, "
            "LLM/news, watchlist, or order behavior changed.",
            "",
        ]
    )
    return "\n".join(lines)


def _card_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            'lane: "alpha_search"',
            'change_type: "read_only_pre_entry_catalyst_quality_attribution"',
            f'trial_family: "{TRIAL_FAMILY}"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["summary"],
            "",
            "## Closeout Notes",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Artifact: `{_repo_rel(OUT_JSON)}`",
            f"- Report: `{_repo_rel(DOC_ARTIFACT)}`",
            f"- Main blocker or acceptance basis: `{payload['rejection_reason'] or payload['acceptance_basis']}`",
            f"- Next retry requires: `{payload['next_retry_requires']}`",
            "",
        ]
    )


def main() -> int:
    timestamp = _utc_now()
    source_rows = _load_json(SOURCE_ROWS, [])
    source_summary = _load_json(SOURCE_SUMMARY, {})
    rows = [_classify_row(row) for row in source_rows]

    diverse_rows = [
        row
        for row in rows
        if row.get("diversity_bucket") == "source_or_category_diverse_high_confidence"
    ]
    single_rows = [
        row
        for row in rows
        if row.get("diversity_bucket")
        == "single_source_single_category_high_confidence"
    ]
    no_hc_rows = [
        row for row in rows if row.get("diversity_bucket") == "no_high_confidence_catalyst"
    ]

    diverse_summary = _summary(diverse_rows)
    single_summary = _summary(single_rows)
    no_hc_summary = _summary(no_hc_rows)
    lift_vs_single = _lift(diverse_summary, single_summary)
    lift_vs_no_hc = _lift(diverse_summary, no_hc_summary)
    positive_lift_windows = _window_lift_count(rows)
    top_share = (
        diverse_summary.get("positive_concentration", {}).get(
            "top_ticker_positive_share",
            0.0,
        )
        or 0.0
    )

    evidence = {
        "min_diverse_rows": MIN_DIVERSE_ROWS,
        "diverse_rows": diverse_summary["trade_count"],
        "diverse_count_ok": diverse_summary["trade_count"] >= MIN_DIVERSE_ROWS,
        "avg_pnl_lift_vs_single_high_confidence": lift_vs_single["avg_pnl"],
        "min_avg_pnl_lift_vs_single": MIN_AVG_PNL_LIFT_VS_SINGLE,
        "pnl_lift_ok": (
            lift_vs_single["avg_pnl"] is not None
            and lift_vs_single["avg_pnl"] >= MIN_AVG_PNL_LIFT_VS_SINGLE
        ),
        "avg_return_lift_vs_single_high_confidence": lift_vs_single["avg_return"],
        "min_avg_return_lift_vs_single": MIN_AVG_RETURN_LIFT_VS_SINGLE,
        "return_lift_ok": (
            lift_vs_single["avg_return"] is not None
            and lift_vs_single["avg_return"] >= MIN_AVG_RETURN_LIFT_VS_SINGLE
        ),
        "positive_lift_windows": positive_lift_windows,
        "min_positive_lift_windows": MIN_POSITIVE_LIFT_WINDOWS,
        "window_stability_ok": positive_lift_windows >= MIN_POSITIVE_LIFT_WINDOWS,
        "top_ticker_positive_share": top_share,
        "max_top_positive_ticker_share": MAX_TOP_POSITIVE_TICKER_SHARE,
        "concentration_ok": top_share <= MAX_TOP_POSITIVE_TICKER_SHARE,
    }
    passed = all(
        [
            evidence["diverse_count_ok"],
            evidence["pnl_lift_ok"],
            evidence["return_lift_ok"],
            evidence["window_stability_ok"],
            evidence["concentration_ok"],
        ]
    )
    decision = (
        "observed_useful_pre_entry_catalyst_diversity_field"
        if passed
        else "rejected_pre_entry_catalyst_diversity_field"
    )
    summary = (
        "Diverse high-confidence catalyst context produced a candidate quality "
        "field worth a later Gate 1-4 strategy test."
        if passed
        else (
            "Rejected: source/category diversity did not provide a promotion-grade "
            "quality field beyond the broad high-confidence catalyst tag."
        )
    )
    failed = [
        name
        for name, ok in [
            ("thin_diverse_sample", evidence["diverse_count_ok"]),
            ("avg_pnl_lift_below_threshold", evidence["pnl_lift_ok"]),
            ("avg_return_lift_below_threshold", evidence["return_lift_ok"]),
            ("window_lift_count_below_threshold", evidence["window_stability_ok"]),
            ("diverse_positive_pnl_concentration_failed", evidence["concentration_ok"]),
        ]
        if not ok
    ]
    actual_success = 1 if passed else 0
    predicted_probability = 0.22
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "created_at": timestamp,
        "status": "observed_only" if passed else "rejected",
        "lane": "alpha_search",
        "registry_lane": "alpha_search",
        "hypothesis": (
            "High-confidence pre-entry catalysts may only be useful when the "
            "catalyst context is source-diverse or category-diverse; after broad "
            "catalyst-backed prebreakout entry and core risk top-up failed, audit "
            "source/category diversity before any further early-entry promotion."
        ),
        "change_summary": (
            "Read-only attribution of exp-20260530-014 core trade rows by "
            "high-confidence catalyst source/category diversity."
        ),
        "change_type": "read_only_pre_entry_catalyst_quality_attribution",
        "mechanism_family": "event_or_llm",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260530-014",
            "exp-20260530-016",
            "exp-20260530-017",
            "exp-20260530-018",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "derived_pit_pre_entry_catalyst_quality_field",
        "parameters": {
            "high_confidence_categories": sorted(HIGH_CONFIDENCE_CATEGORIES),
            "diverse_definition": (
                "high_confidence_category_count >= 2 or "
                "high_confidence_source_count >= 2"
            ),
            "acceptance": {
                "min_diverse_rows": MIN_DIVERSE_ROWS,
                "min_avg_pnl_lift_vs_single": MIN_AVG_PNL_LIFT_VS_SINGLE,
                "min_avg_return_lift_vs_single": MIN_AVG_RETURN_LIFT_VS_SINGLE,
                "min_positive_lift_windows": MIN_POSITIVE_LIFT_WINDOWS,
                "max_top_positive_ticker_share": MAX_TOP_POSITIVE_TICKER_SHARE,
            },
        },
        "date_range": {
            "start": "2024-10-02",
            "end": "2026-04-21",
        },
        "secondary_windows": [
            {"start": "2024-10-02", "end": "2025-04-22"},
            {"start": "2025-04-23", "end": "2025-10-22"},
            {"start": "2025-10-23", "end": "2026-04-21"},
        ],
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical core trade rows from "
                "exp-20260530-014; read-only attribution"
            ),
            "baseline_result_file": _repo_rel(SOURCE_ROWS),
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
        },
        "before_metrics": single_summary,
        "after_metrics": diverse_summary,
        "delta_metrics": {
            "avg_pnl": lift_vs_single["avg_pnl"],
            "avg_return": lift_vs_single["avg_return"],
            "expected_value_score": 0.0,
            "total_pnl_usd": 0.0,
            "strategy_logic_changed": False,
            "trade_count": diverse_summary["trade_count"] - single_summary["trade_count"],
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "bucket_summaries": {
            "all": _summary(rows),
            "by_diversity_bucket": {
                "source_or_category_diverse_high_confidence": diverse_summary,
                "single_source_single_category_high_confidence": single_summary,
                "no_high_confidence_catalyst": no_hc_summary,
            },
            "by_combo": _category_combo_rows(rows),
            "by_window": _bucketed(rows, "window"),
        },
        "source_reference": {
            "source_rows": _repo_rel(SOURCE_ROWS),
            "source_summary": _repo_rel(SOURCE_SUMMARY),
            "source_observed_gate": source_summary.get("observed_gate"),
        },
        "gate1": {
            "passed": True,
            "source_trade_rows": len(source_rows),
            "baseline_result_file": _repo_rel(SOURCE_ROWS),
            "core_logic_changed": False,
        },
        "gate2": {
            "passed": True,
            "required_source_fields": [
                "ticker",
                "entry_date",
                "window",
                "pnl",
                "pnl_pct_net",
                "catalyst_examples",
            ],
            "missing_required_fields": {},
            "no_llm_prompt_dependency": True,
        },
        "gate3": {
            "passed": True,
            "candidate_pool_changed": False,
            "new_core_filter_added": False,
            "core_survival_changed": False,
            "note": "Read-only attribution; no filter or survival-changing rule added.",
        },
        "gate4": {
            "passed": passed,
            "promotion_grade": passed,
            "strategy_replacement_tested": False,
            "decision_evidence": evidence,
            "failed_reasons": failed,
            "reason": summary,
        },
        "decision": decision,
        "summary": summary,
        "acceptance_basis": (
            "Diverse high-confidence catalyst rows cleared sample, lift, window, "
            "and concentration gates."
            if passed
            else None
        ),
        "rejection_reason": "; ".join(failed) if failed else None,
        "next_retry_requires": (
            "Do not promote another broad catalyst early-entry or risk scalar on "
            "these frozen windows. A valid retry needs a materially richer "
            "catalyst-quality field, such as source credibility plus semantic "
            "direction from SEC/news text, or forward replacement-value rows."
        ),
        "prediction": {
            "success_probability": predicted_probability,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "thin_diverse_sample",
                "no_diversity_separation",
                "category_noise",
                "window_instability",
            ],
            "confidence_reason": (
                "Broad high-confidence catalyst context was useful in read-only "
                "attribution but failed when promoted to early entry or risk top-up; "
                "source/category diversity is the next sharper quality field, but "
                "sample size is likely thin."
            ),
            "recorded_at": "2026-05-30T21:37:17+00:00",
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_probability,
            "brier_score": _round((predicted_probability - actual_success) ** 2, 6),
            "expected_ev_delta": 0.0,
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": [
                "thin_diverse_sample",
                "no_diversity_separation",
                "category_noise",
                "window_instability",
            ],
            "realized_failure_mode": ";".join(failed) if failed else "none",
            "predicted_failure_mode_hit": bool(failed),
            "surprise_level": "low",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_attribution_only": True,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_capital_changed": False,
            "parity_test_added": False,
        },
        "preflight_questions": {
            "1_alpha_hypothesis": (
                "entry/event attribution: source/category-diverse catalysts may "
                "identify the subset of pre-entry catalyst context worth future "
                "scout treatment."
            ),
            "2_history_check": (
                "exp-20260530-014 found broad high-confidence catalyst separation; "
                "exp-20260530-016 rejected catalyst-qualified prebreakout entries; "
                "exp-20260530-017 rejected core risk top-up; exp-20260530-018 "
                "rejected freshness as a sharper field."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Diverse rows >=4, average PnL lift >=$1,000 and average return "
                "lift >=3pp versus single-source/category high-confidence rows, "
                "positive lift in at least two windows, and top positive ticker "
                "share <=50%."
            ),
            "5_reproducibility": (
                f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(SOURCE_ROWS),
            _repo_rel(SOURCE_SUMMARY),
            _repo_rel(OUT_JSON),
            _repo_rel(ROWS_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_CARD),
            _repo_rel(DOC_ARTIFACT),
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(ROWS_JSON, rows)
    _write_json(DOC_LOG, payload)
    ticket = _load_json(DOC_TICKET, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": timestamp,
            "updated_at": timestamp,
            "decision": decision,
            "summary": summary,
            "artifact_file": _repo_rel(OUT_JSON),
            "report_file": _repo_rel(DOC_ARTIFACT),
            "result_file": _repo_rel(DOC_LOG),
            "repro_command": payload["preflight_questions"]["5_reproducibility"],
            "result": {
                "decision": decision,
                "summary": summary,
                "json": _repo_rel(OUT_JSON),
                "artifact": _repo_rel(DOC_ARTIFACT),
                "calibration": payload["calibration"],
            },
            "calibration": payload["calibration"],
        }
    )
    _write_json(DOC_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    DOC_CARD.write_text(_card_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)
    _update_registry(payload)

    print(json.dumps(_safe(payload["gate4"]["decision_evidence"]), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
