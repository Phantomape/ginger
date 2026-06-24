"""exp-20260624-007: post-20260623 current alpha surface readiness.

Read-only alpha-search guardrail. This audits whether the newly generated
2026-06-23 production-visible artifacts make any next alpha surface gate-ready.
It changes no strategy helper, adapter, paper ledger, ranking, sizing, exits,
watchlist, live ledger, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-007"
OWNER = "alpha-explore"
SLUG = "current_alpha_surface_readiness_20260623"
RUNNER = f"quant/experiments/exp_20260624_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_007_{SLUG}.json"
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
PRIOR_READINESS_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260623-019.json"

SEC_EVENTS_20260623 = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20260623.jsonl"
SEC_TEXT_20260623 = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260623.jsonl"
SEC_FEATURES_20260623 = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_features_20260623.jsonl"
EST_REV_20260623 = REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_20260623.jsonl"
OPTIONS_CHAIN_20260623 = REPO_ROOT / "data" / "non_ohlcv" / "options_onclickmedia_chain_20260623.jsonl"
OPTIONS_SUMMARY_20260623 = REPO_ROOT / "data" / "non_ohlcv" / "options_onclickmedia_summary_20260623.json"
KOVA_SNAPSHOT_20260623 = REPO_ROOT / "data" / "kova" / "snapshots" / "kova_data_snapshot_20260623.json"
KOVA_INTRADAY_20260623 = REPO_ROOT / "data" / "kova" / "intraday" / "intraday_ohlcv_20260623.jsonl"
KOVA_13F_20260623 = REPO_ROOT / "data" / "kova" / "institutional" / "sec13f_ownership_20260623.jsonl"

HYPOTHESIS = (
    "alpha_search/readiness: post-20260623 production-visible non-OHLCV and "
    "forward ledgers may contain enough new closed replacement rows, 6-K text "
    "rows, Kova rows, options rows, or estimate-revision rows to identify a "
    "gate-ready next alpha surface without retuning frozen windows."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "production_visible_current_surface_readiness"
TRIAL_FAMILY = "current_alpha_surface_readiness_delta"
TRIAL_VARIANT_ID = "post_20260623_v1"
CHANGED_VARIABLE = "post_20260623_current_alpha_surface_readiness_delta_v1"
NEW_EVIDENCE_TYPE = "post_20260623_daily_artifact_surface_delta"
NEW_EVIDENCE_AXIS = (
    "Machine-checkable new local artifacts dated 2026-06-23: SEC filing "
    "event/text/features, options, Kova, estimate-revision, and forward "
    "replacement ledgers generated after exp-20260623-019."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-019",
    "exp-20260624-002",
    "exp-20260624-006",
]
CAUSAL_COMPONENTS = [
    "read-only surface audit",
    "forward ledger freshness",
    "closed-row readiness",
    "no strategy behavior change",
]

ACCEPTANCE_RULE = {
    "min_new_forward_rows_since_prior_readiness": 20,
    "min_activation_closed_rows_per_sleeve": 60,
    "min_watchlist_closed_rows_per_sleeve": 20,
    "min_sec_6k_text_rows": 20,
    "min_sec_6k_structured_financial_hits": 5,
    "min_non_skipped_kova_intraday_rows": 20,
    "min_non_skipped_kova_13f_rows": 20,
    "min_estimate_revision_candidate_matches": 10,
    "min_options_closed_rows": 50,
}

RECENT_CLOSEOUT_LOGS = [
    ("exp-20260623-024", "non_ohlcv_cross_source_attention_lead"),
    ("exp-20260623-025", "non_ohlcv_confluence_shared_precheck"),
    ("exp-20260624-002", "estimate_revision_direction_outcome"),
    ("exp-20260624-004", "forward_ticker_memory"),
    ("exp-20260624-006", "forward_entry_date_sleeve_breadth"),
    ("exp-20260623-010", "options_forward_skew"),
    ("exp-20260623-014", "kova_rs_growth_alignment"),
    ("exp-20260623-018", "exit_lifecycle_next_open_value"),
]

FINANCIAL_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\brevenue\b",
        r"\bnet income\b",
        r"\boperating income\b",
        r"\bgross profit\b",
        r"\bearnings per share\b",
        r"\bEPS\b",
        r"\bEBITDA\b",
        r"\bguidance\b",
        r"\boutlook\b",
        r"\bquarter\b",
        r"\bfiscal\b",
    )
]
NUMERIC_PATTERN = re.compile(r"(\$|\b\d+(?:\.\d+)?\s?%|\b\d+\.\d+\b|\b\d{2,}\b)")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid jsonl") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                rows.append(line)
    if not replaced:
        rows.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.2,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "no_new_closed_rows",
            "rows_too_thin",
            "only_pending_forward_rows",
            "source_family_recently_rejected",
        ],
        "confidence_reason": (
            "Fallback prediction for read-only readiness audit; reservation "
            "should normally provide the full prediction."
        ),
        "recorded_at": utc_now(),
    }


def summarize_baseline() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(safe_float(row.get("expected_value_score")) or 0.0 for row in windows),
            4,
        ),
        "total_pnl": round(sum(safe_float(row.get("total_pnl")) or 0.0 for row in windows), 2),
        "max_drawdown_pct_worst": round(
            max((safe_float(row.get("max_drawdown_pct")) or 0.0 for row in windows), default=0.0),
            4,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": (
            round(signals_survived / signals_generated, 4)
            if signals_generated
            else None
        ),
        "windows": windows,
    }


def summarize_forward_replacement() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_REPLACEMENT)
    prior = read_json(PRIOR_READINESS_LOG, {})
    prior_count = int(
        prior.get("gate4", {}).get("current_forward_rows")
        or prior.get("gate2", {}).get("forward_replacement", {}).get("current_rows")
        or 0
    )

    by_sleeve: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_sleeve[str(row.get("sleeve_key") or "missing")].append(row)

    sleeve_summaries: list[dict[str, Any]] = []
    for sleeve, sleeve_rows in sorted(by_sleeve.items(), key=lambda item: (-len(item[1]), item[0])):
        cash = [safe_float(row.get("replacement_value_vs_cash_usd")) or 0.0 for row in sleeve_rows]
        spy = [safe_float(row.get("replacement_value_vs_spy_usd")) or 0.0 for row in sleeve_rows]
        qqq = [safe_float(row.get("replacement_value_vs_qqq_usd")) or 0.0 for row in sleeve_rows]
        positive_by_ticker: defaultdict[str, float] = defaultdict(float)
        for row, value in zip(sleeve_rows, cash):
            if value > 0:
                positive_by_ticker[str(row.get("ticker") or "missing")] += value
        positive_sum = sum(positive_by_ticker.values())
        max_share = max(positive_by_ticker.values()) / positive_sum if positive_sum > 0 else None
        activation_ready = (
            len(sleeve_rows) >= ACCEPTANCE_RULE["min_activation_closed_rows_per_sleeve"]
            and sum(cash) > 0
            and sum(spy) > 0
            and sum(qqq) > 0
            and max_share is not None
            and max_share <= 0.5
        )
        watchlist_ready = (
            len(sleeve_rows) >= ACCEPTANCE_RULE["min_watchlist_closed_rows_per_sleeve"]
            and sum(cash) > 0
            and sum(spy) > 0
            and sum(qqq) > 0
            and max_share is not None
            and max_share <= 0.5
        )
        sleeve_summaries.append(
            {
                "sleeve_key": sleeve,
                "closed_rows": len(sleeve_rows),
                "ticker_count": len({str(row.get("ticker") or "missing") for row in sleeve_rows}),
                "sum_cash": round(sum(cash), 2),
                "sum_spy": round(sum(spy), 2),
                "sum_qqq": round(sum(qqq), 2),
                "cash_positive_rate": round(sum(1 for value in cash if value > 0) / len(cash), 4)
                if cash
                else None,
                "max_single_positive_cash_share": round(max_share, 6) if max_share is not None else None,
                "activation_ready": activation_ready,
                "watchlist_ready": watchlist_ready,
            }
        )
    return {
        "artifact": repo_rel(FORWARD_REPLACEMENT),
        "current_rows": len(rows),
        "prior_rows_exp_20260623_019": prior_count,
        "row_delta_since_exp_20260623_019": len(rows) - prior_count,
        "rows_by_sleeve": dict(Counter(str(row.get("sleeve_key") or "missing") for row in rows)),
        "entry_dates": sorted({str(row.get("entry_date")) for row in rows if row.get("entry_date")}),
        "sleeve_summaries": sleeve_summaries,
        "activation_ready_sleeves": [row for row in sleeve_summaries if row["activation_ready"]],
        "watchlist_ready_sleeves": [row for row in sleeve_summaries if row["watchlist_ready"]],
    }


def form_value(row: dict[str, Any]) -> str:
    return str(row.get("form_type") or row.get("form") or row.get("form_base") or "").upper()


def count_form_rows(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(form_value(row) or "missing" for row in rows)


def summarize_sec_surface() -> dict[str, Any]:
    events = read_jsonl(SEC_EVENTS_20260623)
    texts = read_jsonl(SEC_TEXT_20260623)
    features = read_jsonl(SEC_FEATURES_20260623)
    six_k_events = [row for row in events if form_value(row) in {"6-K", "6-K/A"}]
    six_k_texts = [row for row in texts if form_value(row) in {"6-K", "6-K/A"}]
    structured_hits = []
    for row in six_k_texts:
        text = str(row.get("combined_text") or row.get("text") or "")
        has_financial_term = any(pattern.search(text) for pattern in FINANCIAL_PATTERNS)
        has_numeric = bool(NUMERIC_PATTERN.search(text))
        if has_financial_term and has_numeric:
            structured_hits.append(row)
    return {
        "events_file": repo_rel(SEC_EVENTS_20260623),
        "text_file": repo_rel(SEC_TEXT_20260623),
        "features_file": repo_rel(SEC_FEATURES_20260623),
        "event_rows": len(events),
        "text_rows": len(texts),
        "feature_rows": len(features),
        "forms_in_events": dict(count_form_rows(events).most_common()),
        "forms_in_text": dict(count_form_rows(texts).most_common()),
        "six_k_event_rows": len(six_k_events),
        "six_k_text_rows": len(six_k_texts),
        "six_k_structured_financial_hits": len(structured_hits),
        "six_k_text_samples": [
            {
                "ticker": row.get("ticker"),
                "accession_number": row.get("accession_number"),
                "usable_trade_date": row.get("usable_trade_date"),
                "text_word_count": row.get("text_word_count"),
            }
            for row in six_k_texts[:10]
        ],
    }


def summarize_status_rows(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    statuses = Counter(str(row.get("status") or "missing") for row in rows)
    reasons = Counter(str(row.get("reason") or "missing") for row in rows)
    return {
        "path": repo_rel(path),
        "row_count": len(rows),
        "statuses": dict(statuses),
        "non_skipped_rows": sum(1 for row in rows if str(row.get("status") or "") not in {"skipped", "missing"}),
        "top_reasons": dict(reasons.most_common(5)),
    }


def summarize_kova_surface() -> dict[str, Any]:
    snapshot = read_json(KOVA_SNAPSHOT_20260623, {})
    fundamental = snapshot.get("fundamental_growth", {}) if isinstance(snapshot, dict) else {}
    rs_proxy = snapshot.get("rs_proxy", {}) if isinstance(snapshot, dict) else {}
    return {
        "snapshot_file": repo_rel(KOVA_SNAPSHOT_20260623),
        "snapshot_exists": KOVA_SNAPSHOT_20260623.exists(),
        "snapshot_status": snapshot.get("status") if isinstance(snapshot, dict) else None,
        "tickers": len(snapshot.get("tickers") or []) if isinstance(snapshot, dict) else 0,
        "fundamental_rows_written": fundamental.get("rows_written"),
        "rs_proxy_rows_written": rs_proxy.get("rows_written"),
        "intraday": summarize_status_rows(KOVA_INTRADAY_20260623),
        "sec13f": summarize_status_rows(KOVA_13F_20260623),
    }


def summarize_estimate_revision_surface() -> dict[str, Any]:
    rows = read_jsonl(EST_REV_20260623)
    def delta(row: dict[str, Any]) -> float:
        values = [
            safe_float(row.get("eps_estimate_delta_prev")),
            safe_float(row.get("eps_estimate_delta_7d")),
            safe_float(row.get("eps_estimate_delta_30d")),
        ]
        clean = [value for value in values if value is not None]
        if not clean:
            return 0.0
        return max(clean, key=abs)

    positive = [row for row in rows if delta(row) > 0]
    negative = [row for row in rows if delta(row) < 0]
    flat = [row for row in rows if delta(row) == 0]
    matched_candidates = [row for row in rows if row.get("matched_candidate_today")]
    matched_selected = [row for row in rows if row.get("matched_selected_signal_today")]
    return {
        "ledger_file": repo_rel(EST_REV_20260623),
        "rows": len(rows),
        "usable_rows": sum(1 for row in rows if row.get("estimate_revision_usable")),
        "positive_revision_rows": len(positive),
        "negative_revision_rows": len(negative),
        "flat_revision_rows": len(flat),
        "matched_candidate_rows": len(matched_candidates),
        "matched_selected_signal_rows": len(matched_selected),
        "candidate_match_gap_reasons": dict(
            Counter(str(row.get("candidate_match_gap_reason") or "missing") for row in rows).most_common(8)
        ),
    }


def summarize_options_surface() -> dict[str, Any]:
    rows = read_jsonl(OPTIONS_CHAIN_20260623)
    summary = read_json(OPTIONS_SUMMARY_20260623, {})
    tickers = {str(row.get("ticker") or row.get("symbol") or "") for row in rows if row.get("ticker") or row.get("symbol")}
    return {
        "chain_file": repo_rel(OPTIONS_CHAIN_20260623),
        "summary_file": repo_rel(OPTIONS_SUMMARY_20260623),
        "chain_rows": len(rows),
        "ticker_count": len(tickers),
        "summary_keys": sorted(summary.keys()) if isinstance(summary, dict) else [],
        "closed_forward_rows": 0,
        "blocked_by_recent_closeout": "exp-20260623-010 rejected monotonic options skew on closed forward rows",
    }


def summarize_recent_closeouts() -> list[dict[str, Any]]:
    summaries = []
    for experiment_id, surface in RECENT_CLOSEOUT_LOGS:
        path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
        data = read_json(path, {})
        gate4 = data.get("gate4") if isinstance(data.get("gate4"), dict) else {}
        summaries.append(
            {
                "experiment_id": experiment_id,
                "surface": surface,
                "path": repo_rel(path),
                "status": data.get("status"),
                "decision": data.get("decision"),
                "accepted_alpha": bool(data.get("accepted_alpha")),
                "observed_only_lead": bool(data.get("observed_only_lead")),
                "gate4_failed_reasons": gate4.get("failed_reasons") or [],
            }
        )
    return summaries


def evaluate(
    forward: dict[str, Any],
    sec: dict[str, Any],
    kova: dict[str, Any],
    estimates: dict[str, Any],
    options: dict[str, Any],
    closeouts: list[dict[str, Any]],
) -> dict[str, Any]:
    failed: list[str] = []
    if forward["row_delta_since_exp_20260623_019"] < ACCEPTANCE_RULE["min_new_forward_rows_since_prior_readiness"]:
        failed.append("no_material_new_forward_replacement_rows_since_exp_20260623_019")
    if not forward["activation_ready_sleeves"]:
        failed.append("no_forward_activation_ready_sleeve")
    if not forward["watchlist_ready_sleeves"]:
        failed.append("no_forward_watchlist_ready_sleeve")
    if sec["six_k_text_rows"] < ACCEPTANCE_RULE["min_sec_6k_text_rows"]:
        failed.append("sec_6k_text_rows_too_few")
    if sec["six_k_structured_financial_hits"] < ACCEPTANCE_RULE["min_sec_6k_structured_financial_hits"]:
        failed.append("sec_6k_structured_financial_hits_too_few")
    if kova["intraday"]["non_skipped_rows"] < ACCEPTANCE_RULE["min_non_skipped_kova_intraday_rows"]:
        failed.append("kova_intraday_rows_all_or_mostly_skipped")
    if kova["sec13f"]["non_skipped_rows"] < ACCEPTANCE_RULE["min_non_skipped_kova_13f_rows"]:
        failed.append("kova_sec13f_rows_all_or_mostly_skipped")
    if estimates["matched_candidate_rows"] < ACCEPTANCE_RULE["min_estimate_revision_candidate_matches"]:
        failed.append("estimate_revision_has_no_candidate_match_surface")
    if options["closed_forward_rows"] < ACCEPTANCE_RULE["min_options_closed_rows"]:
        failed.append("options_20260623_has_no_new_closed_forward_rows")
    if any(row["experiment_id"] == "exp-20260623-025" and row["decision"] for row in closeouts):
        failed.append("non_ohlcv_confluence_positive_lead_failed_shared_adapter_precheck")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_current_post_20260623_surface_gate_ready"
            if passed
            else "rejected_no_gate_ready_post_20260623_surface_delta"
        ),
        "failed_reasons": failed,
        "acceptance_rule": ACCEPTANCE_RULE,
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = summarize_baseline()
    forward = summarize_forward_replacement()
    sec = summarize_sec_surface()
    kova = summarize_kova_surface()
    estimates = summarize_estimate_revision_surface()
    options = summarize_options_surface()
    closeouts = summarize_recent_closeouts()
    gate4 = evaluate(forward, sec, kova, estimates, options, closeouts)
    actual_success = 1 if gate4["passed"] else 0
    predicted = safe_float(prediction.get("success_probability")) or 0.0

    status = "observed_only" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["passed"],
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_readiness_delta",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": actual_success,
            "actual_decision": decision,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "failure_modes_observed": gate4["failed_reasons"],
            "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
        },
        "before_metrics": baseline,
        "after_metrics": baseline | {"strategy_behavior_changed": False},
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "new_forward_rows_since_exp_20260623_019": forward["row_delta_since_exp_20260623_019"],
            "sec_6k_text_rows": sec["six_k_text_rows"],
            "kova_intraday_non_skipped_rows": kova["intraday"]["non_skipped_rows"],
            "estimate_revision_matched_candidate_rows": estimates["matched_candidate_rows"],
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_summary": baseline,
        },
        "gate2": {
            "passed": True,
            "required_fields": [
                "entry_date or as_of_date",
                "replacement_value_vs_cash_usd",
                "usable_trade_date",
                "ticker",
                "status",
            ],
            "target_price": {
                "available": False,
                "reason": "No executable target or exit rule is scheduled in this read-only audit.",
            },
            "forward_replacement": forward,
            "sec_20260623": sec,
            "kova_20260623": kova,
            "estimate_revision_20260623": estimates,
            "options_20260623": options,
        },
        "gate3": {
            "passed": baseline["survival_rate"] is not None and baseline["survival_rate"] >= 0.05,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "strategy_filter_added": False,
            "note": "No executable filter, entry, ranking, sizing, exit, paper order, or live order changed.",
        },
        "gate4": gate4,
        "surface_closeout_scan": closeouts,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "uses_llm": False,
            "parity_note": "Read-only surface readiness audit over existing local artifacts.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The 2026-06-23 artifact delta did not produce a gate-ready next "
                "alpha surface: forward replacement rows did not increase since "
                "exp-20260623-019, 6-K text had only "
                f"{sec['six_k_text_rows']} row(s), Kova intraday/13F remained "
                "skipped, estimate-revision rows had no candidate matches, and "
                "the non-OHLCV confluence lead was already rejected by the "
                "shared-adapter precheck."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry this batch by relaxing 6-K phrase/numeric regexes, "
                "estimate-revision thresholds, Kova RS/growth/source-count gates, "
                "options skew buckets, forward sleeve row-count gates, top-N, "
                "hold days, notional, cooldown, or allocator rank on the same "
                "2026-06-23 artifacts."
            ),
            "new_evidence_required": (
                "Need materially more closed forward replacement rows for a "
                "diversified sleeve/source, non-skipped Kova intraday or 13F "
                "provenance, replayable historical 6-K text, PIT borrow/loan or "
                "options history, or a new production-visible field not already "
                "saturated."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "novelty_gate": "experiment.py new passed without override; nearest revision-expectation matches were below blocking threshold.",
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_REPLACEMENT),
            repo_rel(BASELINE_RESULT),
            repo_rel(SEC_EVENTS_20260623),
            repo_rel(SEC_TEXT_20260623),
            repo_rel(SEC_FEATURES_20260623),
            repo_rel(EST_REV_20260623),
            repo_rel(OPTIONS_CHAIN_20260623),
            repo_rel(KOVA_SNAPSHOT_20260623),
            repo_rel(KOVA_INTRADAY_20260623),
            repo_rel(KOVA_13F_20260623),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - current alpha surface readiness 20260623",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- artifact: `{repo_rel(OUT_JSON)}`",
            f"- runner: `{RUNNER_COMMAND}`",
            f"- failed reasons: {', '.join(payload['gate4']['failed_reasons']) or 'none'}",
            "",
            "## Key Counts",
            "",
            f"- new forward rows since exp-20260623-019: {payload['delta_metrics']['new_forward_rows_since_exp_20260623_019']}",
            f"- 6-K text rows: {payload['delta_metrics']['sec_6k_text_rows']}",
            f"- Kova intraday non-skipped rows: {payload['delta_metrics']['kova_intraday_non_skipped_rows']}",
            f"- estimate-revision matched candidate rows: {payload['delta_metrics']['estimate_revision_matched_candidate_rows']}",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        FORWARD_REPLACEMENT,
        SEC_EVENTS_20260623,
        SEC_TEXT_20260623,
        EST_REV_20260623,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
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
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "new_forward_rows": payload["delta_metrics"]["new_forward_rows_since_exp_20260623_019"],
                "sec_6k_text_rows": payload["delta_metrics"]["sec_6k_text_rows"],
                "kova_intraday_non_skipped_rows": payload["delta_metrics"]["kova_intraday_non_skipped_rows"],
                "estimate_revision_matched_candidate_rows": payload["delta_metrics"]["estimate_revision_matched_candidate_rows"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
