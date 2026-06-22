"""exp-20260622-013: forward replacement activation readiness audit.

Read-only alpha search. After exp-20260622-012 repaired missing SPY/QQQ
comparator replacement values, the current forward replacement artifact is
fully enriched. This runner tests whether any default-off paper sleeve/source
family now has enough closed replacement-value evidence to justify a separate
production activation-envelope experiment.

Reproduce:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260622_013_forward_replacement_activation_readiness_20260622.py
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import forward_replacement_value as frv  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260622-013"
LANE = "alpha_search"
STEM = "forward_replacement_activation_readiness_20260622"
RUNNER = f"quant/experiments/exp_20260622_013_{STEM}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "codex-alpha-explore"

FORWARD_ARTIFACT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260622_013_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Forward replacement rows fully enriched after exp-20260622-012 may identify "
    "a default-off paper sleeve/source family that is ready for a production "
    "activation-envelope test using positive replacement value versus cash, SPY, "
    "and QQQ."
)
CHANGED_VARIABLE = "comparator_enriched_forward_replacement_activation_readiness_v1"
TRIAL_FAMILY = "default_off_forward_replacement_value_activation_readiness"
TRIAL_VARIANT_ID = "comparator_enriched_current_artifact_20260622_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260605-028",
    "exp-20260608-021",
    "exp-20260622-011",
    "exp-20260622-012",
]

MIN_ACTIVATION_ROWS = 60
MIN_WATCHLIST_ROWS = 20
MIN_WIN_RATE = 0.50
MAX_SINGLE_POSITIVE_SHARE = 0.50
MIN_ENTRY_SPAN_DAYS = 20

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "closed_rows_too_few",
        "single_ticker_concentration",
        "negative_replacement_vs_etfs",
        "source_family_immature",
    ],
    "confidence_reason": (
        "exp-20260622-012 created the first all-enriched current forward "
        "replacement artifact, but only 33 total rows exist and prior readiness "
        "audits were blocked by thin/concentrated samples; success needs a "
        "sleeve family with enough rows and positive value versus cash, SPY, "
        "and QQQ."
    ),
    "recorded_at": "2026-06-22T13:03:56+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": HYPOTHESIS,
    "2_history_check": {
        "exp-20260605-028": "Rejected activation readiness: closed rows too few and low_deployment ETF was QQQ-concentrated.",
        "exp-20260608-021": "Rejected activation readiness through 2026-06-07: no new mature closed-row delta.",
        "exp-20260622-011": "Accepted measurement refresh but left four rows missing SPY/QQQ comparator bars.",
        "exp-20260622-012": "Accepted comparator-session repair; all 33 current rows are now enriched.",
        "novelty_gate": "Reservation passed; new evidence axis is the now fully comparator-enriched forward artifact.",
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "A sleeve/source family is activation-envelope-ready only if the current "
        "forward artifact is all enriched, it has at least 60 closed rows, "
        "positive aggregate replacement value versus cash/SPY/QQQ, win rate "
        "versus each comparator is at least 50%, max single positive ticker "
        "share is at most 50%, and rows span at least 20 calendar days. "
        "A 20-row tier is only a watchlist, not activation-ready."
    ),
    "5_reproducibility": RUNNER_COMMAND,
}

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": False,
    "trade_enabled": False,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "uses_llm": False,
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "Read-only forward readiness audit. It consumes the current replacement "
        "artifact and does not change helper logic, snapshots, orders, ranking, "
        "sizing, exits, LLM/news, or live/default behavior."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, Path):
        return _repo_rel(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
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
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _date_value(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _baseline_summary() -> dict[str, Any]:
    data = _load_json(BASELINE_PATH)
    windows = data.get("windows") or []
    return {
        "path": _repo_rel(BASELINE_PATH),
        "windows": [
            {
                "label": row.get("label"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
            for row in windows
        ],
        "aggregate_expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "aggregate_total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in windows),
        "total_trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
    }


def _artifact_state_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    state_records, skipped_missing = frv.current_state_replacement_records(SLEEVES_ROOT)
    state_keys = {frv.replacement_artifact_key(row) for row in state_records}
    artifact_keys = {frv.replacement_artifact_key(row) for row in rows}
    missing_comparator_rows = [
        row
        for row in rows
        if row.get("status") != "enriched"
        or row.get("replacement_value_vs_spy_usd") is None
        or row.get("replacement_value_vs_qqq_usd") is None
    ]
    return {
        "artifact_rows": len(rows),
        "state_replacement_rows": len(state_records),
        "rows_by_status": dict(Counter(str(row.get("status") or "unknown") for row in rows)),
        "rows_by_sleeve": dict(Counter(str(row.get("sleeve_key") or "unknown") for row in rows)),
        "missing_comparator_bar_rows": len(missing_comparator_rows),
        "skipped_closed_rows_missing_replacement": len(skipped_missing),
        "rows_not_in_current_state": [
            {
                "sleeve_key": row.get("sleeve_key"),
                "decision_id": row.get("decision_id"),
                "ticker": row.get("ticker"),
                "status": row.get("status"),
            }
            for row in rows
            if frv.replacement_artifact_key(row) not in state_keys
        ],
        "state_rows_missing_artifact": [
            {
                "sleeve_key": row.get("sleeve_key"),
                "decision_id": row.get("decision_id"),
                "ticker": row.get("ticker"),
                "status": row.get("status"),
            }
            for row in state_records
            if frv.replacement_artifact_key(row) not in artifact_keys
        ],
    }


def _group_summary(group_key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "replacement_value_vs_cash_usd",
        "replacement_value_vs_spy_usd",
        "replacement_value_vs_qqq_usd",
    ]
    totals = {field: round(sum(_number(row, field) for row in rows), 2) for field in fields}
    medians = {field: _median([_number(row, field) for row in rows]) for field in fields}
    win_rates = {
        field: round(sum(1 for row in rows if _number(row, field) > 0.0) / len(rows), 4)
        for field in fields
    }
    positive_by_ticker: Counter[str] = Counter()
    for row in rows:
        value = _number(row, "replacement_value_vs_cash_usd")
        if value > 0:
            positive_by_ticker[str(row.get("ticker") or "unknown")] += value
    positive_total = sum(positive_by_ticker.values())
    max_single_positive_share = (
        max(positive_by_ticker.values()) / positive_total if positive_total > 0 else None
    )
    dates = [item for item in (_date_value(row.get("entry_date")) for row in rows) if item is not None]
    entry_span_days = (max(dates) - min(dates)).days if dates else 0
    tickers = Counter(str(row.get("ticker") or "unknown") for row in rows)

    blockers = []
    if len(rows) < MIN_ACTIVATION_ROWS:
        blockers.append("closed_rows_below_activation_min")
    if any(totals[field] <= 0.0 for field in fields):
        blockers.append("nonpositive_replacement_value")
    if any(win_rates[field] < MIN_WIN_RATE for field in fields):
        blockers.append("win_rate_below_min")
    if max_single_positive_share is None or max_single_positive_share > MAX_SINGLE_POSITIVE_SHARE:
        blockers.append("single_ticker_positive_share_failed")
    if entry_span_days < MIN_ENTRY_SPAN_DAYS:
        blockers.append("entry_span_too_short")

    watchlist_blockers = [
        blocker
        for blocker in blockers
        if blocker != "closed_rows_below_activation_min"
    ]
    if len(rows) < MIN_WATCHLIST_ROWS:
        watchlist_blockers.append("closed_rows_below_watchlist_min")

    return {
        "key": group_key,
        "closed_rows": len(rows),
        "tickers": dict(tickers),
        "entry_date_min": min((row.get("entry_date") for row in rows if row.get("entry_date")), default=None),
        "entry_date_max": max((row.get("entry_date") for row in rows if row.get("entry_date")), default=None),
        "entry_span_days": entry_span_days,
        "totals": totals,
        "medians": medians,
        "win_rates": win_rates,
        "positive_by_ticker_cash": {key: round(value, 2) for key, value in positive_by_ticker.items()},
        "max_single_positive_share_cash": (
            round(max_single_positive_share, 6) if max_single_positive_share is not None else None
        ),
        "activation_ready": not blockers,
        "watchlist_ready": not watchlist_blockers,
        "activation_blockers": blockers,
        "watchlist_blockers": watchlist_blockers,
    }


def _summaries_by(rows: list[dict[str, Any]], key_name: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key_name) or "unknown")].append(row)
    summaries = [_group_summary(key, grouped[key]) for key in sorted(grouped)]
    return sorted(summaries, key=lambda item: (-item["closed_rows"], item["key"]))


def _source_key(row: dict[str, Any]) -> str:
    decision_id = str(row.get("decision_id") or "")
    if ":" in decision_id:
        return decision_id.split(":", 1)[0]
    return str(row.get("sleeve_key") or "unknown")


def _source_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_source_key(row)].append(row)
    return sorted(
        [_group_summary(key, grouped[key]) for key in sorted(grouped)],
        key=lambda item: (-item["closed_rows"], item["key"]),
    )


def _overall_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _group_summary("all_forward_rows", rows)
    summary["rows_by_sleeve"] = dict(Counter(str(row.get("sleeve_key") or "unknown") for row in rows))
    return summary


def _gate4(
    rows: list[dict[str, Any]],
    sleeve_summaries: list[dict[str, Any]],
    source_summaries: list[dict[str, Any]],
    artifact_audit: dict[str, Any],
) -> dict[str, Any]:
    activation_candidates = [
        item for item in [*sleeve_summaries, *source_summaries] if item["activation_ready"]
    ]
    watchlist_candidates = [
        item for item in [*sleeve_summaries, *source_summaries] if item["watchlist_ready"]
    ]
    failed = []
    if artifact_audit["missing_comparator_bar_rows"] != 0:
        failed.append("artifact_has_missing_comparator_rows")
    if artifact_audit["skipped_closed_rows_missing_replacement"] != 0:
        failed.append("state_has_closed_rows_missing_replacement")
    if artifact_audit["rows_not_in_current_state"] or artifact_audit["state_rows_missing_artifact"]:
        failed.append("state_artifact_reconciliation_failed")
    if not activation_candidates:
        failed.append("no_activation_ready_sleeve_or_source_family")
    if max((item["closed_rows"] for item in sleeve_summaries), default=0) < MIN_ACTIVATION_ROWS:
        failed.append("closed_rows_too_few")
    if not watchlist_candidates:
        failed.append("no_20_row_watchlist_candidate")

    return {
        "passed": not failed,
        "decision": (
            "accepted_activation_envelope_candidate_after_comparator_repair"
            if not failed
            else "rejected_no_forward_activation_ready_after_comparator_repair"
        ),
        "failed_reasons": failed,
        "activation_thresholds": {
            "min_activation_closed_rows": MIN_ACTIVATION_ROWS,
            "min_watchlist_closed_rows": MIN_WATCHLIST_ROWS,
            "min_win_rate": MIN_WIN_RATE,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "min_entry_span_days": MIN_ENTRY_SPAN_DAYS,
        },
        "activation_candidates": activation_candidates,
        "watchlist_candidates": watchlist_candidates,
        "artifact_all_enriched": artifact_audit["missing_comparator_bar_rows"] == 0,
        "total_forward_rows": len(rows),
    }


def _calibration(gate4: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4["passed"] else 0
    predicted = float(PREDICTION["success_probability"])
    failures = list(gate4.get("failed_reasons") or [])
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual_success) ** 2, 6),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": 0.0,
        "ev_prediction_error": 0.0,
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": 0.0,
        "pnl_prediction_error": 0.0,
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "failure_modes_observed": failures,
        "predicted_failure_mode_hit": any(
            failure in failures
            for failure in [
                "closed_rows_too_few",
                "no_activation_ready_sleeve_or_source_family",
                "no_20_row_watchlist_candidate",
            ]
        ),
        "surprise_note": (
            "Low surprise. Comparator repair made the artifact usable, but no "
            "sleeve/source family has enough diversified closed rows for an "
            "activation-envelope test."
            if failures
            else "The enriched forward artifact produced an activation-envelope candidate."
        ),
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    rows = _load_jsonl(FORWARD_ARTIFACT)
    baseline = _baseline_summary()
    artifact_audit = _artifact_state_audit(rows)
    sleeve_summaries = _summaries_by(rows, "sleeve_key")
    source_summaries = _source_summaries(rows)
    gate4 = _gate4(rows, sleeve_summaries, source_summaries, artifact_audit)
    status = "accepted_paper_pending_activation_envelope" if gate4["passed"] else "rejected"
    calibration = _calibration(gate4)
    overall = _overall_summary(rows)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": LANE,
        "status": status,
        "decision": gate4["decision"],
        "accepted": gate4["passed"],
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_summary": (
            "Audit the fully enriched current forward replacement-value artifact "
            "for default-off sleeve/source-family activation readiness."
        ),
        "change_type": "default_off_forward_readiness_audit",
        "implementation_mode": "observed_only_forward_readiness_audit",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "forward replacement artifact audit",
            "source-family replacement-value gates",
            "activation blocker report",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "comparator_enriched_forward_replacement_rows",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "parameters": gate4["activation_thresholds"],
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(BASELINE_PATH),
            "baseline_metrics": baseline,
            "note": "Strategy baseline is recorded for context; no before/after strategy replay changed.",
        },
        "gate2": {
            "passed": artifact_audit["missing_comparator_bar_rows"] == 0,
            "runtime_fields_checked": [
                "entry_date",
                "exit_date",
                "notional_usd",
                "pnl_usd",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "target_price_scope": (
                "Not required for this closed forward replacement artifact; "
                "activation readiness is based on realized entry/exit rows and "
                "does not create a new executable policy."
            ),
            "artifact_audit": artifact_audit,
        },
        "gate3": {
            "passed": baseline["min_survival_rate"] >= 0.05,
            "baseline_min_survival_rate": baseline["min_survival_rate"],
            "new_core_filter_added": False,
            "note": "No filter, entry rule, ranking, or core candidate pool changed.",
        },
        "gate4": gate4,
        "overall_forward_replacement_summary": overall,
        "sleeve_summaries": sleeve_summaries,
        "source_summaries": source_summaries,
        "before_metrics": {
            "aggregate_expected_value_score": baseline["aggregate_expected_value_score"],
            "aggregate_total_pnl": baseline["aggregate_total_pnl"],
            "artifact_rows": len(rows),
            "activation_ready_groups": 0,
        },
        "after_metrics": {
            "aggregate_expected_value_score": baseline["aggregate_expected_value_score"],
            "aggregate_total_pnl": baseline["aggregate_total_pnl"],
            "artifact_rows": len(rows),
            "activation_ready_groups": len(gate4["activation_candidates"]),
            "watchlist_ready_groups": len(gate4["watchlist_candidates"]),
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "artifact_rows": 0,
            "activation_ready_groups": len(gate4["activation_candidates"]),
        },
        "production_impact": PRODUCTION_IMPACT,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "post_run_reflection": {
            "why_result_happened": (
                "The comparator repair was useful measurement work: all 33 rows "
                "are now enriched. The alpha/readiness result is still negative "
                "because the only moderately populated sleeve is low_deployment_etf "
                "with 17 QQQ-only rows, while the strongest stock sleeve, "
                "state_surface, has only 3 closed rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun forward activation readiness, relax the 60-row "
                "minimum, or retune low_deployment/state_surface thresholds until "
                "new closed replacement-value rows arrive. Do not treat QQQ-only "
                "low_deployment rows as diversified live evidence."
            ),
            "new_evidence_required": (
                "At least 20-60 additional enriched closed forward rows for a "
                "single helper/source family, diversified across tickers, with "
                "positive replacement value versus cash, SPY, and QQQ. A "
                "state_surface-specific follow-up needs forward rows, not frozen "
                "window re-slicing."
            ),
        },
        "next_retry_requires": [
            "materially more enriched closed forward rows",
            "diversified positive replacement value by sleeve/source family",
            "no relaxation of low_deployment ETF concentration gates",
        ],
        "rejection_reason": "; ".join(gate4["failed_reasons"]) if not gate4["passed"] else None,
        "related_files": [
            RUNNER,
            _repo_rel(FORWARD_ARTIFACT),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": RUNNER,
        "parameters": payload["parameters"],
        "date_range": {"start": "2026-05-05", "end": "2026-06-18"},
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "decision_basis": (
            "Rejected because no sleeve/source family met activation readiness "
            "despite the artifact now being fully enriched."
            if not payload["accepted"]
            else "Accepted as an activation-envelope candidate; live still requires a separate release decision."
        ),
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": payload["anti_js"],
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Sleeve | Rows | Cash RV | SPY RV | QQQ RV | Cash win | Max ticker share | Blockers |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in payload["sleeve_summaries"]:
        rows.append(
            "| {key} | {rows} | ${cash:,.2f} | ${spy:,.2f} | ${qqq:,.2f} | {win:.1%} | {share} | {blockers} |".format(
                key=item["key"],
                rows=item["closed_rows"],
                cash=item["totals"]["replacement_value_vs_cash_usd"],
                spy=item["totals"]["replacement_value_vs_spy_usd"],
                qqq=item["totals"]["replacement_value_vs_qqq_usd"],
                win=item["win_rates"]["replacement_value_vs_cash_usd"],
                share=(
                    "n/a"
                    if item["max_single_positive_share_cash"] is None
                    else f"{item['max_single_positive_share_cash']:.1%}"
                ),
                blockers=", ".join(item["activation_blockers"]) or "none",
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: forward replacement activation readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Trade enabled: false",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Readiness Table",
            "",
            *rows,
            "",
            "## Gate 4",
            "",
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "- Artifact rows: `{}`".format(payload["gate4"]["total_forward_rows"]),
            "- Activation candidates: `{}`".format(len(payload["gate4"]["activation_candidates"])),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        FORWARD_ARTIFACT,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            _repo_rel(path): {"exists": path.exists(), "sha256": _sha256(path)}
            for path in files
        },
        "anti_js": payload["anti_js"],
        "updated_at": _utc_now(),
    }


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "runner": RUNNER,
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
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
            "baseline_result_file": _repo_rel(BASELINE_PATH),
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate_expected_value_score"],
            "aggregate_strategy_total_pnl_delta": payload["delta_metrics"]["aggregate_total_pnl"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": [
                RUNNER,
                "data/experiments/exp-20260622-013/",
                "experiments/logs/exp-20260622-013.json",
                "experiments/cards/exp-20260622-013.md",
                "experiments/manifests/exp-20260622-013.json",
                "experiments/tickets/exp-20260622-013.json",
                "docs/experiment_log.jsonl",
                "docs/experiment_registry.json",
            ],
            "related_files": payload["related_files"],
        },
    )
    _write_json(MANIFEST_JSON, _build_manifest(payload))


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact_rows": payload["gate4"]["total_forward_rows"],
                "activation_candidates": len(payload["gate4"]["activation_candidates"]),
                "watchlist_candidates": len(payload["gate4"]["watchlist_candidates"]),
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "anti_js": payload["anti_js"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
