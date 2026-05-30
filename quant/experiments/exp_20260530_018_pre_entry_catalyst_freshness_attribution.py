"""exp-20260530-018: pre-entry catalyst freshness attribution.

Read-only follow-up to exp-20260530-014. The experiment checks whether
high-confidence catalyst events that are fresh (<= 3 calendar days before core
entry) separate better than stale or absent high-confidence catalyst context.

No production strategy, backtester, ranking, sizing, exits, LLM/news, or order
path is changed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "exp-20260530-018"
STEM = "pre_entry_catalyst_freshness_attribution"
RULE_VERSION = "high_confidence_pre_entry_catalyst_freshness_bucket_v1"
FRESH_MAX_CALENDAR_DAYS = 3
MIN_FRESH_ROWS = 8
MIN_AVG_PNL_LIFT = 500.0
MIN_AVG_RETURN_LIFT = 0.05
MAX_TOP_POSITIVE_TICKER_SHARE = 0.50

SOURCE_ROWS_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260530-014"
    / "pre_entry_catalyst_attribution_trade_rows.json"
)
SOURCE_SUMMARY_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260530-014"
    / "exp_20260530_014_pre_entry_catalyst_attribution.json"
)
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
WINDOWS = ["old_thin", "mid_weak", "late_strong"]

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
ROWS_JSON = OUT_DIR / f"{STEM}_rows.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _round(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parse_date(value: Any) -> date | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        pnl = float(row.get("pnl") or 0.0)
        if pnl > 0:
            by_ticker[str(row.get("ticker") or "")] += pnl
    total = sum(by_ticker.values())
    ranked = [
        {
            "ticker": ticker,
            "positive_pnl": _round(value, 4),
            "share": _round(value / total, 6) if total else None,
        }
        for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "positive_pnl_total": _round(total, 4),
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_share": ranked[0]["share"] if ranked else None,
        "by_ticker": ranked[:20],
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "trade_count": 0,
            "total_pnl": 0.0,
            "avg_pnl": None,
            "median_pnl": None,
            "avg_return": None,
            "win_rate": None,
            "positive_concentration": _positive_concentration([]),
        }
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    returns = [float(row.get("pnl_pct_net") or 0.0) for row in rows]
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnls), 4),
        "avg_pnl": _round(sum(pnls) / len(pnls), 4),
        "median_pnl": _round(median(pnls), 4),
        "avg_return": _round(sum(returns) / len(returns), 6),
        "win_rate": _round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 6),
        "positive_concentration": _positive_concentration(rows),
    }


def _freshness_features(row: dict[str, Any]) -> dict[str, Any]:
    entry_date = _parse_date(row.get("entry_date"))
    high_conf_events: list[dict[str, Any]] = []
    ages: list[int] = []
    for event in row.get("catalyst_examples") or []:
        if not isinstance(event, dict) or not event.get("high_confidence"):
            continue
        event_date = _parse_date(event.get("date"))
        if entry_date is None or event_date is None:
            continue
        age = (entry_date - event_date).days
        if age < 0:
            continue
        event_copy = dict(event)
        event_copy["age_days_before_entry"] = age
        high_conf_events.append(event_copy)
        ages.append(age)

    freshest_age = min(ages) if ages else None
    if freshest_age is None:
        bucket = "no_high_confidence_catalyst"
    elif freshest_age <= FRESH_MAX_CALENDAR_DAYS:
        bucket = "fresh_high_confidence_catalyst"
    else:
        bucket = "stale_high_confidence_catalyst"
    return {
        "freshness_bucket": bucket,
        "fresh_high_confidence_catalyst": bucket == "fresh_high_confidence_catalyst",
        "stale_or_no_high_confidence_catalyst": bucket != "fresh_high_confidence_catalyst",
        "freshest_high_confidence_catalyst_age_days": freshest_age,
        "high_confidence_catalyst_event_ages_days": sorted(ages),
        "high_confidence_catalyst_examples": high_conf_events[:8],
        "fresh_max_calendar_days": FRESH_MAX_CALENDAR_DAYS,
        "rule_version": RULE_VERSION,
        "known_at": "after_catalyst_event_date_and_before_existing_core_entry_closeout_attribution",
    }


def _analyze_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = _load_json(SOURCE_ROWS_JSON)
    if not isinstance(raw, list):
        raise ValueError(f"expected list at {_repo_rel(SOURCE_ROWS_JSON)}")
    rows: list[dict[str, Any]] = []
    missing = Counter()
    for item in raw:
        if not isinstance(item, dict):
            continue
        for field in ("ticker", "entry_date", "window", "pnl", "pnl_pct_net"):
            if item.get(field) in (None, ""):
                missing[field] += 1
        enriched = {**item, **_freshness_features(item)}
        rows.append(enriched)
    audit = {
        "source_file": _repo_rel(SOURCE_ROWS_JSON),
        "source_summary_file": _repo_rel(SOURCE_SUMMARY_JSON),
        "source_trade_rows": len(raw),
        "analyzed_trade_rows": len(rows),
        "missing_required_fields": dict(sorted(missing.items())),
        "rule": {
            "fresh_max_calendar_days": FRESH_MAX_CALENDAR_DAYS,
            "basis": "minimum high-confidence catalyst event date age before existing core entry_date",
        },
    }
    return rows, audit


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = [
        "fresh_high_confidence_catalyst",
        "stale_high_confidence_catalyst",
        "no_high_confidence_catalyst",
    ]
    by_bucket = {
        bucket: _summary([row for row in rows if row["freshness_bucket"] == bucket])
        for bucket in buckets
    }
    fresh_rows = [row for row in rows if row.get("fresh_high_confidence_catalyst")]
    stale_or_none = [
        row for row in rows if row.get("stale_or_no_high_confidence_catalyst")
    ]
    by_window: dict[str, dict[str, Any]] = {}
    for window in WINDOWS:
        window_rows = [row for row in rows if row.get("window") == window]
        by_window[window] = {
            "all": _summary(window_rows),
            "fresh_high_confidence_catalyst": _summary(
                [row for row in window_rows if row.get("fresh_high_confidence_catalyst")]
            ),
            "stale_or_no_high_confidence_catalyst": _summary(
                [row for row in window_rows if row.get("stale_or_no_high_confidence_catalyst")]
            ),
        }
    return {
        "all": _summary(rows),
        "fresh_high_confidence_catalyst": _summary(fresh_rows),
        "stale_or_no_high_confidence_catalyst": _summary(stale_or_none),
        "by_freshness_bucket": by_bucket,
        "by_window": by_window,
    }


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "path": _repo_rel(OPEN_POSITIONS_JSON), "missing_file": True}
    payload = _load_json(OPEN_POSITIONS_JSON)
    rows = []
    if isinstance(payload, dict):
        for key in ("observations", "positions"):
            value = payload.get(key)
            if isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, dict))
    missing: dict[str, list[str]] = {}
    for field in ("entry_date", "target_price"):
        bad = [
            str(row.get("ticker") or "<unknown>")
            for row in rows
            if row.get(field) in (None, "")
        ]
        if bad:
            missing[field] = bad
    return {
        "passed": not missing,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_like_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_fields": missing,
    }


def _decision(summary: dict[str, Any]) -> tuple[str, str, dict[str, Any], str, str | None]:
    fresh = summary["fresh_high_confidence_catalyst"]
    stale_or_none = summary["stale_or_no_high_confidence_catalyst"]
    count_ok = fresh["trade_count"] >= MIN_FRESH_ROWS
    avg_pnl_lift = (
        fresh["avg_pnl"] - stale_or_none["avg_pnl"]
        if fresh["avg_pnl"] is not None and stale_or_none["avg_pnl"] is not None
        else None
    )
    avg_return_lift = (
        fresh["avg_return"] - stale_or_none["avg_return"]
        if fresh["avg_return"] is not None and stale_or_none["avg_return"] is not None
        else None
    )
    pnl_lift_ok = avg_pnl_lift is not None and avg_pnl_lift >= MIN_AVG_PNL_LIFT
    return_lift_ok = (
        avg_return_lift is not None and avg_return_lift >= MIN_AVG_RETURN_LIFT
    )
    concentration_share = fresh["positive_concentration"]["top_ticker_positive_share"]
    concentration_ok = (
        concentration_share is not None
        and concentration_share <= MAX_TOP_POSITIVE_TICKER_SHARE
    )
    window_lift_count = 0
    for row in summary["by_window"].values():
        fresh_window = row["fresh_high_confidence_catalyst"]
        other_window = row["stale_or_no_high_confidence_catalyst"]
        if (
            fresh_window["avg_pnl"] is not None
            and other_window["avg_pnl"] is not None
            and fresh_window["avg_pnl"] > other_window["avg_pnl"]
        ):
            window_lift_count += 1
    window_stability_ok = window_lift_count >= 2
    passed = (
        count_ok
        and pnl_lift_ok
        and return_lift_ok
        and concentration_ok
        and window_stability_ok
    )
    evidence = {
        "field_candidate_passed": passed,
        "fresh_trade_count": fresh["trade_count"],
        "min_fresh_rows": MIN_FRESH_ROWS,
        "fresh_count_ok": count_ok,
        "avg_pnl_lift_vs_stale_or_no_high_confidence": _round(avg_pnl_lift, 4),
        "min_avg_pnl_lift": MIN_AVG_PNL_LIFT,
        "pnl_lift_ok": pnl_lift_ok,
        "avg_return_lift_vs_stale_or_no_high_confidence": _round(avg_return_lift, 6),
        "min_avg_return_lift": MIN_AVG_RETURN_LIFT,
        "return_lift_ok": return_lift_ok,
        "top_ticker_positive_share": concentration_share,
        "max_top_positive_ticker_share": MAX_TOP_POSITIVE_TICKER_SHARE,
        "concentration_ok": concentration_ok,
        "window_lift_count": window_lift_count,
        "min_window_lift_count": 2,
        "window_stability_ok": window_stability_ok,
    }
    if passed:
        return (
            "observed_only_candidate_pre_entry_catalyst_freshness_field",
            "observed_only",
            evidence,
            (
                "Fresh high-confidence pre-entry catalysts cleared the observed-only "
                "sample, lift, concentration, and multi-window gates. This is not a "
                "promotion; it only nominates a later production-visible timing gate "
                "or replacement-value test."
            ),
            None,
        )
    failed_parts = [
        key
        for key, ok in {
            "fresh_count": count_ok,
            "avg_pnl_lift": pnl_lift_ok,
            "avg_return_lift": return_lift_ok,
            "positive_pnl_concentration": concentration_ok,
            "window_stability": window_stability_ok,
        }.items()
        if not ok
    ]
    reason = (
        "Rejected: fresh high-confidence catalyst timing did not clear "
        + ", ".join(failed_parts)
        + "."
    )
    return (
        "rejected_pre_entry_catalyst_freshness_field",
        "rejected",
        evidence,
        reason,
        reason,
    )


def _existing_ticket() -> dict[str, Any]:
    if TICKET_JSON.exists():
        data = _load_json(TICKET_JSON)
        return data if isinstance(data, dict) else {}
    return {}


def _calibration(
    ticket: dict[str, Any],
    actual_success: int,
    decision: str,
    rejection_reason: str | None,
) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else {}
    probability = float(prediction.get("success_probability") or 0.0)
    brier = (probability - actual_success) ** 2
    reason = rejection_reason or ""
    if "fresh_count" in reason:
        realized = "thin_fresh_sample"
    elif "avg_pnl" in reason or "avg_return" in reason:
        realized = "no_freshness_separation"
    elif "concentration" in reason:
        realized = "single_ticker_concentration"
    elif "window" in reason:
        realized = "window_instability"
    else:
        realized = None
    failure_modes = prediction.get("main_failure_modes") or []
    return {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": _round(probability, 6),
        "brier_score": _round(brier, 6),
        "calibration_direction": (
            "directionally_calibrated" if actual_success == 0 and probability < 0.5 else "overconfident"
        ),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": failure_modes,
        "realized_failure_mode": realized,
        "predicted_failure_mode_hit": realized in failure_modes if realized else None,
        "surprise_level": "low" if actual_success == 0 else "medium",
    }


def _build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    created_at = _now()
    ticket = _existing_ticket()
    rows, audit = _analyze_rows()
    summary = _summaries(rows)
    decision, status, evidence, summary_text, rejection_reason = _decision(summary)
    actual_success = 1 if evidence["field_candidate_passed"] else 0
    open_positions_audit = _audit_open_positions()
    before_metrics = summary["stale_or_no_high_confidence_catalyst"]
    after_metrics = summary["fresh_high_confidence_catalyst"]
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(SOURCE_ROWS_JSON),
        _repo_rel(SOURCE_SUMMARY_JSON),
        _repo_rel(OUT_JSON),
        _repo_rel(ROWS_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(DOCS_TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(MANIFEST_JSON),
    ]
    return (
        {
            "experiment_id": EXPERIMENT_ID,
            "created_at": created_at,
            "timestamp": created_at,
            "status": status,
            "decision": decision,
            "lane": "alpha_discovery",
            "registry_lane": "alpha_discovery",
            "hypothesis": ticket.get("hypothesis")
            or "Fresh pre-entry high-confidence catalysts may improve core entry timing attribution.",
            "change_summary": (
                "Read-only attribution of exp-20260530-014 core trade rows by "
                "fresh high-confidence catalyst age <=3 calendar days before entry "
                "versus stale or absent high-confidence catalyst context."
            ),
            "change_type": "read_only_pre_entry_catalyst_timing_attribution",
            "mechanism_family": "event_or_llm",
            "trial_family": "pre_entry_catalyst_freshness_attribution",
            "trial_variant_id": RULE_VERSION,
            "changed_variable": RULE_VERSION,
            "single_causal_variable": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260530-014",
                "exp-20260530-016",
                "exp-20260530-017",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "derived_pit_pre_entry_catalyst_timing_field",
            "summary": summary_text,
            "source_audit": audit,
            "preflight_questions": {
                "1_alpha_hypothesis": (
                    "entry/event attribution: fresh high-confidence catalyst context "
                    "may be more actionable than stale catalyst context for already "
                    "executed core trend/breakout entries."
                ),
                "2_history_check": (
                    "exp-20260530-014 found high-confidence catalyst context useful "
                    "but did not test freshness; exp-20260530-016 and 017 rejected "
                    "promotion attempts from the broad catalyst tag."
                ),
                "3_single_causal_variable": RULE_VERSION,
                "4_acceptance_standard": (
                    "Fresh rows >=8, >=$500 average PnL lift and >=5pp average return "
                    "lift versus stale/no-high-confidence rows, at least two windows "
                    "with positive lift, and tagged positive PnL max single-ticker "
                    "share <=50%."
                ),
                "5_reproducibility": (
                    ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260530_018_pre_entry_catalyst_freshness_attribution.py"
                ),
            },
            "backtest_protocol": {
                "source": "docs/backtesting.md canonical core trade rows from exp-20260530-014; read-only attribution",
                "baseline_result_file": _repo_rel(SOURCE_ROWS_JSON),
                "strategy_replacement_tested": False,
                "changed_core_logic": False,
            },
            "gate1": {
                "passed": SOURCE_ROWS_JSON.exists() and audit["analyzed_trade_rows"] > 0,
                "baseline_result_file": _repo_rel(SOURCE_ROWS_JSON),
                "source_trade_rows": audit["source_trade_rows"],
                "analyzed_trade_rows": audit["analyzed_trade_rows"],
                "core_logic_changed": False,
            },
            "gate2": {
                "passed": open_positions_audit.get("passed") is True
                and not audit["missing_required_fields"],
                "open_positions": open_positions_audit,
                "source_fields": {
                    "required_source_fields": [
                        "ticker",
                        "entry_date",
                        "window",
                        "pnl",
                        "pnl_pct_net",
                        "catalyst_examples",
                    ],
                    "missing_required_fields": audit["missing_required_fields"],
                    "analyzed_trade_rows": audit["analyzed_trade_rows"],
                },
                "required_runtime_fields": ["entry_date", "target_price"],
                "no_llm_prompt_dependency": True,
            },
            "gate3": {
                "passed": True,
                "new_core_filter_added": False,
                "candidate_pool_changed": False,
                "core_survival_changed": False,
                "note": "Read-only attribution; no filter or survival-changing rule added.",
            },
            "gate4": {
                "passed": evidence["field_candidate_passed"],
                "strategy_replacement_tested": False,
                "promotion_grade": False,
                "decision_evidence": evidence,
                "reason": rejection_reason,
            },
            "parameters": {
                "rule_version": RULE_VERSION,
                "fresh_max_calendar_days": FRESH_MAX_CALENDAR_DAYS,
                "min_fresh_rows": MIN_FRESH_ROWS,
                "min_avg_pnl_lift": MIN_AVG_PNL_LIFT,
                "min_avg_return_lift": MIN_AVG_RETURN_LIFT,
                "max_top_positive_ticker_share": MAX_TOP_POSITIVE_TICKER_SHARE,
            },
            "date_range": {"start": "2024-10-02", "end": "2026-04-21"},
            "secondary_windows": [
                {"start": "2025-04-23", "end": "2025-10-22"},
                {"start": "2025-10-23", "end": "2026-04-21"},
            ],
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
            "delta_metrics": {
                "avg_pnl": evidence["avg_pnl_lift_vs_stale_or_no_high_confidence"],
                "avg_return": evidence["avg_return_lift_vs_stale_or_no_high_confidence"],
                "trade_count": after_metrics["trade_count"] - before_metrics["trade_count"],
                "expected_value_score": 0.0,
                "total_pnl_usd": 0.0,
                "strategy_logic_changed": False,
            },
            "bucket_summaries": summary,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_attribution_only": True,
                "orders_changed": False,
                "live_capital_changed": False,
                "trade_enabled": False,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_exits": False,
                "alters_orders": False,
            },
            "prediction": ticket.get("prediction"),
            "calibration": _calibration(ticket, actual_success, decision, rejection_reason),
            "rejection_reason": rejection_reason,
            "next_retry_requires": []
            if actual_success
            else [
                "larger forward sample of production-visible high-confidence catalyst rows",
                "source-diversity or catalyst-quality evidence beyond simple freshness",
                "replacement-value test before any timing gate or risk allocation",
            ],
            "related_files": related_files,
            "repro_command": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260530_018_pre_entry_catalyst_freshness_attribution.py"
            ),
            "artifacts": {
                "json": _repo_rel(OUT_JSON),
                "rows": _repo_rel(ROWS_JSON),
                "log": _repo_rel(LOG_JSON),
                "ticket": _repo_rel(TICKET_JSON),
                "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
                "card": _repo_rel(CARD_MD),
                "markdown": _repo_rel(ARTIFACT_MD),
                "manifest": _repo_rel(MANIFEST_JSON),
            },
            "why_not_other_changes": (
                "Skipped SEC sector-event breadth because exp-20260530-012 already "
                "rejected it; skipped same-ticker SEC recurrence because exp-006/008/009 "
                "rejected it; skipped broad catalyst promotion because exp-016/017 "
                "already failed. This tests a new timing attribution field only."
            ),
            "anti_js": "No JavaScript was used.",
        },
        rows,
    )


def _build_report(payload: dict[str, Any]) -> str:
    evidence = payload["gate4"]["decision_evidence"]
    lines = [
        f"# {EXPERIMENT_ID} Pre-Entry Catalyst Freshness Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Gate 4 Evidence",
        "",
        "```json",
        json.dumps(evidence, indent=2, sort_keys=True),
        "```",
        "",
        "## Freshness Buckets",
        "",
        "| bucket | trades | avg pnl | avg return | win rate | top positive share |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket, row in payload["bucket_summaries"]["by_freshness_bucket"].items():
        lines.append(
            "| {bucket} | {count} | {avg_pnl} | {avg_return} | {win_rate} | {share} |".format(
                bucket=bucket,
                count=row["trade_count"],
                avg_pnl=row["avg_pnl"],
                avg_return=row["avg_return"],
                win_rate=row["win_rate"],
                share=row["positive_concentration"]["top_ticker_positive_share"],
            )
        )
    lines.extend(
        [
            "",
            "## Window Summary",
            "",
            "| window | fresh trades | fresh avg pnl | stale/no-HC avg pnl | fresh win rate | stale/no-HC win rate |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for window, row in payload["bucket_summaries"]["by_window"].items():
        lines.append(
            "| {window} | {fc} | {fp} | {op} | {fw} | {ow} |".format(
                window=window,
                fc=row["fresh_high_confidence_catalyst"]["trade_count"],
                fp=row["fresh_high_confidence_catalyst"]["avg_pnl"],
                op=row["stale_or_no_high_confidence_catalyst"]["avg_pnl"],
                fw=row["fresh_high_confidence_catalyst"]["win_rate"],
                ow=row["stale_or_no_high_confidence_catalyst"]["win_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Repro",
            "",
            "```powershell",
            payload["repro_command"],
            "```",
            "",
            "## Related Files",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _build_card(payload: dict[str, Any]) -> str:
    evidence = payload["gate4"]["decision_evidence"]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        f'experiment_uid: "{_existing_ticket().get("experiment_uid")}"',
        f'status: "{payload["status"]}"',
        'lane: "alpha_discovery"',
        'change_type: "read_only_pre_entry_catalyst_timing_attribution"',
        'mechanism_family: "event_or_llm"',
        'trial_family: "pre_entry_catalyst_freshness_attribution"',
        f'trial_variant_id: "{RULE_VERSION}"',
        f'changed_variable: "{RULE_VERSION}"',
        'new_evidence_type: "derived_pit_pre_entry_catalyst_timing_field"',
        f'updated_at: "{payload["created_at"]}"',
        'hub_repo_id: "ginger/experiments/exp-20260530-018"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Summary",
        "",
        payload["summary"],
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Fresh high-confidence trades: `{evidence['fresh_trade_count']}`",
        f"- Avg PnL lift vs stale/no-HC: `{evidence['avg_pnl_lift_vs_stale_or_no_high_confidence']}`",
        f"- Avg return lift vs stale/no-HC: `{evidence['avg_return_lift_vs_stale_or_no_high_confidence']}`",
        f"- Window lift count: `{evidence['window_lift_count']}`",
        "",
        "## Reserved Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    registry = _load_json(EXPERIMENT_REGISTRY) if EXPERIMENT_REGISTRY.exists() else {}
    if not isinstance(registry, dict):
        registry = {}
    registry.setdefault("schema_version", 1)
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": payload["registry_lane"],
        "owner": ticket.get("owner") or "codex",
        "hypothesis": payload["hypothesis"],
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "log_file": _repo_rel(LOG_JSON),
        "updated_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["summary"],
        },
    }
    for idx, item in enumerate(experiments):
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**item, **row}
            break
    else:
        experiments.append(row)
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _save_manifest(ticket: dict[str, Any]) -> None:
    from scripts.experiment_registry import save_revision_manifest

    save_revision_manifest(
        ticket,
        repo_root=REPO_ROOT,
        ticket_file=TICKET_JSON,
        card_file=CARD_MD,
        overwrite=True,
    )


def _persist(payload: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    existing = _existing_ticket()
    ticket = {
        **existing,
        "artifact_file": _repo_rel(OUT_JSON),
        "baseline_result_file": _repo_rel(SOURCE_ROWS_JSON),
        "change_type": payload["change_type"],
        "completed_at": payload["created_at"],
        "decision": payload["decision"],
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "owner": existing.get("owner") or "codex",
        "prior_trial_count": payload["prior_trial_count"],
        "result_file": _repo_rel(LOG_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "status": payload["status"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "updated_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "calibration": payload["calibration"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
    }
    _write_json(OUT_JSON, payload)
    _write_json(ROWS_JSON, {"experiment_id": EXPERIMENT_ID, "rows": rows})
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_json(DOCS_TICKET_JSON, ticket)
    _write_text(CARD_MD, _build_card(payload))
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload, ticket)
    _save_manifest(ticket)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()
    payload, rows = _build_payload()
    if not args.no_persist:
        _persist(payload, rows)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "gate2_passed": payload["gate2"]["passed"],
                "gate4_passed": payload["gate4"]["passed"],
                "analyzed_trade_rows": payload["source_audit"]["analyzed_trade_rows"],
                "fresh_trade_count": payload["gate4"]["decision_evidence"]["fresh_trade_count"],
                "avg_pnl_lift_vs_stale_or_no_high_confidence": payload["gate4"][
                    "decision_evidence"
                ]["avg_pnl_lift_vs_stale_or_no_high_confidence"],
                "avg_return_lift_vs_stale_or_no_high_confidence": payload["gate4"][
                    "decision_evidence"
                ]["avg_return_lift_vs_stale_or_no_high_confidence"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
