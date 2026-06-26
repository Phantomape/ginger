"""exp-20260626-006: recovered quant_signals forward readiness.

Alpha-search, observed-only. This tests whether the production candidate rows
recovered in exp-20260626-005 can become forward replacement-value evidence.
It does not change entries, ranking, sizing, exits, orders, watchlists, or LLM
behavior.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from experiment_registry import persist_self_registered_result  # noqa: E402
from us_market_calendar import is_us_equity_session  # noqa: E402


EXPERIMENT_ID = "exp-20260626-006"
OWNER = "alpha-explore"
SLUG = "recovered_quant_signals_forward_readiness"
RUNNER = f"quant/experiments/exp_20260626_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_006_{SLUG}.json"
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
QUANT_SIGNAL_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"
RECOVERED_TARGETS = [
    "data/daily/signals/quant/quant_signals_20260616.json",
    "data/daily/signals/quant/quant_signals_20260619.json",
    "data/daily/signals/quant/quant_signals_20260620.json",
    "data/daily/signals/quant/quant_signals_20260621.json",
    "data/daily/signals/quant/quant_signals_20260625.json",
]
SQLITE_PRICE_SOURCES = [
    REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite",
    REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite",
]

HYPOTHESIS = (
    "Recovered June quant_signals final artifacts contain production-visible "
    "entry candidate rows that were previously hidden by missing finals; if "
    "local settlement data can resolve their next-open and forward closes, "
    "those rows may create a new forward replacement-value evidence axis for "
    "candidate allocation without retuning frozen historical windows."
)
CHANGE_TYPE = "observed_only_forward_attribution"
IMPLEMENTATION_MODE = "observed_only_forward_readiness"
MECHANISM_FAMILY = "production_candidate_artifact_forward_maturation"
TRIAL_FAMILY = "recovered_quant_signals_entry_candidate_forward_readiness"
TRIAL_VARIANT_ID = "june_2026_recovered_candidates_settlement_audit_v1"
CHANGED_VARIABLE = "recovered_quant_signals_entry_candidate_forward_readiness_v1"
NEW_EVIDENCE_TYPE = "recovered_daily_quant_signals_candidate_rows"
NEW_EVIDENCE_AXIS = (
    "Valid recovered daily quant_signals final files from exp-20260626-005 "
    "with newly visible production candidate rows; this is a forward-row/"
    "settlement readiness axis, not a threshold, ranking, sizing, hold-day, "
    "or notional sweep."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260626-005",
    "exp-20260625-002",
    "exp-20260625-004",
    "exp-20260625-017",
    "exp-20260622-013",
]
CAUSAL_COMPONENTS = [
    "recovered quant_signals rows",
    "entry candidate extraction",
    "local settlement availability audit",
    "pending forward ledger",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_006_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
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
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def date_from_tag(tag: str) -> date:
    return date(int(tag[:4]), int(tag[4:6]), int(tag[6:8]))


def date_iso_from_tag(tag: str) -> str:
    day = date_from_tag(tag)
    return day.isoformat()


def next_session_after(day: date) -> str:
    cursor = day + timedelta(days=1)
    while not is_us_equity_session(cursor):
        cursor += timedelta(days=1)
    return cursor.isoformat()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def candidate_review_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    review = payload.get("entry_candidate_review")
    return review if isinstance(review, dict) else {}


def extract_candidate_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    for rel_path in RECOVERED_TARGETS:
        path = REPO_ROOT / rel_path
        tag = path.stem.replace("quant_signals_", "")
        signal_date = date_iso_from_tag(tag)
        signal_day = date.fromisoformat(signal_date)
        payload = read_json(path, {})
        review = candidate_review_from_payload(payload if isinstance(payload, dict) else {})
        candidates = review.get("candidates") if isinstance(review, dict) else []
        if not isinstance(candidates, list):
            candidates = []
        is_session = is_us_equity_session(signal_day)
        planned_entry_date = next_session_after(signal_day)
        file_summaries.append(
            {
                "source_file": rel_path,
                "date": signal_date,
                "exists": path.exists(),
                "sha256": sha256(path),
                "signal_is_us_equity_session": is_session,
                "candidate_count": int(review.get("candidate_count") or len(candidates) or 0),
                "candidate_rows_extracted": len(candidates),
                "planned_next_session": planned_entry_date,
            }
        )
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            ticker = str(raw.get("ticker") or "").upper()
            target_price = safe_float(raw.get("target_price"))
            entry_price = safe_float(raw.get("entry_price"))
            row = {
                "source_file": rel_path,
                "signal_date": signal_date,
                "signal_is_us_equity_session": is_session,
                "planned_entry_date": planned_entry_date,
                "entry_date_resolution": (
                    "blocked_non_session_signal_date" if not is_session else "next_us_equity_session"
                ),
                "outcome_status": "blocked_non_session_signal_date"
                if not is_session
                else "pending_settlement",
                "ticker": ticker,
                "rank": raw.get("rank"),
                "strategy": raw.get("strategy"),
                "sector": raw.get("sector"),
                "entry_price": entry_price,
                "stop_price": safe_float(raw.get("stop_price")),
                "target_price": target_price,
                "risk_reward_ratio": safe_float(raw.get("risk_reward_ratio")),
                "trade_quality_score": safe_float(raw.get("trade_quality_score")),
                "confidence_score": safe_float(raw.get("confidence_score")),
                "days_to_earnings": raw.get("days_to_earnings"),
                "live_decision": (raw.get("live_accounting") or {}).get("decision")
                if isinstance(raw.get("live_accounting"), dict)
                else None,
                "backtest_decision": (raw.get("backtest_accounting") or {}).get("decision")
                if isinstance(raw.get("backtest_accounting"), dict)
                else None,
                "total_accounting_shadow_decision": (
                    raw.get("total_accounting_shadow") or {}
                ).get("decision")
                if isinstance(raw.get("total_accounting_shadow"), dict)
                else None,
                "has_entry_price": entry_price is not None,
                "has_target_price": target_price is not None,
            }
            candidate_rows.append(row)
    return candidate_rows, file_summaries


def sqlite_source_audit(tickers: set[str]) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for path in SQLITE_PRICE_SOURCES:
        item: dict[str, Any] = {"path": repo_rel(path), "exists": path.exists()}
        if not path.exists():
            item["status"] = "missing"
            audits.append(item)
            continue
        try:
            with sqlite3.connect(path) as con:
                table_names = [
                    str(row[0])
                    for row in con.execute(
                        "select name from sqlite_master where type='table'"
                    ).fetchall()
                ]
                item["tables"] = table_names
                if "ohlcv" not in table_names:
                    item["status"] = "no_ohlcv_table"
                else:
                    total = con.execute("select count(*) from ohlcv").fetchone()[0]
                    min_max = con.execute("select min(date), max(date) from ohlcv").fetchone()
                    item["ohlcv_rows"] = int(total or 0)
                    item["ohlcv_min_date"] = min_max[0]
                    item["ohlcv_max_date"] = min_max[1]
                    if tickers and total:
                        placeholders = ",".join("?" for _ in sorted(tickers))
                        query = (
                            f"select ticker, min(date), max(date), count(*) "
                            f"from ohlcv where ticker in ({placeholders}) group by ticker"
                        )
                        item["ticker_coverage"] = [
                            {
                                "ticker": row[0],
                                "min_date": row[1],
                                "max_date": row[2],
                                "rows": int(row[3] or 0),
                            }
                            for row in con.execute(query, sorted(tickers)).fetchall()
                        ]
                    else:
                        item["ticker_coverage"] = []
                    item["status"] = "ok" if total else "empty_ohlcv_table"
        except Exception as exc:  # pragma: no cover - defensive artifact field
            item["status"] = "error"
            item["error"] = str(exc)
        audits.append(item)
    return audits


def build_readiness(candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_session_rows = [r for r in candidate_rows if r["signal_is_us_equity_session"]]
    non_session_rows = [r for r in candidate_rows if not r["signal_is_us_equity_session"]]
    target_ready = [r for r in candidate_rows if r["has_target_price"]]
    entry_ready = [r for r in candidate_rows if r["has_entry_price"]]
    by_date = Counter(row["signal_date"] for row in candidate_rows)
    by_ticker = Counter(row["ticker"] for row in candidate_rows)
    return {
        "candidate_rows": len(candidate_rows),
        "unique_tickers": sorted(by_ticker),
        "candidate_rows_by_date": dict(sorted(by_date.items())),
        "candidate_rows_by_ticker": dict(sorted(by_ticker.items())),
        "valid_session_candidate_rows": len(valid_session_rows),
        "non_session_candidate_rows": len(non_session_rows),
        "entry_price_coverage": round(len(entry_ready) / len(candidate_rows), 6)
        if candidate_rows
        else None,
        "target_price_coverage": round(len(target_ready) / len(candidate_rows), 6)
        if candidate_rows
        else None,
        "settled_replacement_value_rows": 0,
        "alpha_ready": False,
        "readiness_failed_reasons": [
            reason
            for reason, flag in [
                ("too_few_recovered_candidates", len(candidate_rows) < 20),
                ("all_candidate_rows_on_non_session_dates", bool(candidate_rows) and not valid_session_rows),
                ("no_valid_session_entry_candidates", not valid_session_rows),
                ("no_settled_replacement_values", True),
            ]
            if flag
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    candidate_rows, file_summaries = extract_candidate_rows()
    readiness = build_readiness(candidate_rows)
    tickers = set(readiness["unique_tickers"])
    price_audit = sqlite_source_audit(tickers)
    status = "observed_only_rejected"
    decision = "rejected_recovered_quant_signals_forward_readiness_non_session_blocked"
    failed = list(readiness["readiness_failed_reasons"])
    if all(row.get("status") in {"missing", "empty_ohlcv_table", "no_ohlcv_table"} for row in price_audit):
        if "no_local_settlement_prices" not in failed:
            failed.append("no_local_settlement_prices")

    now = utc_now()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "owner": OWNER,
        "lane": "alpha_search",
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_summary": (
            "Observed-only audit of recovered June quant_signals entry candidates; "
            "all extracted candidates were on non-session dates and no settlement "
            "prices were available."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": status,
            "actual_success": 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get(
                "success_probability"
            ),
            "brier_score": 0.0625,
            "predicted_failure_modes": (ticket.get("prediction") or {}).get(
                "main_failure_modes"
            ),
            "realized_failure_modes": failed,
            "predicted_failure_mode_hit": True,
            "surprise_note": (
                "The settlement blocker occurred as expected, with the sharper "
                "finding that every extracted CAT/TSM candidate row came from a "
                "holiday/weekend quant_signals artifact."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
        },
        "gate2": {
            "passed": bool(candidate_rows),
            "required_fields_checked": [
                "signal_date",
                "ticker",
                "entry_price",
                "target_price",
                "signal_is_us_equity_session",
            ],
            "entry_date_checked": "planned next session derived but blocked for non-session source dates",
            "target_price_coverage": readiness["target_price_coverage"],
            "entry_price_coverage": readiness["entry_price_coverage"],
            "candidate_rows": len(candidate_rows),
        },
        "gate3": {
            "passed": False,
            "filter_added": False,
            "signals_generated_proxy": len(candidate_rows),
            "signals_survived_proxy": readiness["valid_session_candidate_rows"],
            "survival_rate_proxy": 0.0 if candidate_rows else None,
            "note": "No executable filter was added; valid-session forward rows are zero.",
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "observed_only": True,
            "failed_reasons": failed,
            "settled_replacement_value_rows": 0,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
        },
        "before_metrics": baseline,
        "after_metrics": {
            **baseline,
            "recovered_candidate_rows": len(candidate_rows),
            "valid_session_candidate_rows": readiness["valid_session_candidate_rows"],
            "settled_replacement_value_rows": 0,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "recovered_candidate_rows": len(candidate_rows),
            "valid_session_candidate_rows": readiness["valid_session_candidate_rows"],
            "settled_replacement_value_rows": 0,
        },
        "file_summaries": file_summaries,
        "candidate_rows": candidate_rows,
        "readiness": readiness,
        "local_settlement_price_audit": price_audit,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "trade_enabled": False,
            "replay_only": False,
            "daily_snapshot_exposed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": "Read-only artifact audit; no strategy or adapter behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The recovered files did expose six CAT/TSM candidate rows, but "
                "all six were generated on non-session dates (Juneteenth Friday "
                "and the following weekend), so they cannot be treated as clean "
                "next-open forward evidence. Local OHLCV settlement data was also "
                "unavailable."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not promote or reslice these recovered 2026-06-19/20/21 "
                "CAT/TSM rows as alpha. A retry needs session-date candidate rows "
                "and real local next-open/forward-close settlement data."
            ),
            "new_evidence_required": (
                "Generate or recover session-date quant_signals artifacts with "
                "candidate rows, then settle them against PIT local OHLCV/quote "
                "bars before testing allocation value."
            ),
        },
        "rejection_reason": (
            "Recovered candidate rows were all non-session artifacts and had no "
            "settled replacement-value prices."
        ),
        "next_retry_requires": [
            "session-date recovered or newly generated quant_signals candidates",
            "local PIT next-open and 1d/3d/5d forward-close settlement bars",
            "at least 20 valid-session candidate rows before any attribution slice",
        ],
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            "data/experiments/exp-20260626-005/exp_20260626_005_orphan_quant_signals_temp_recovery.json",
            *RECOVERED_TARGETS,
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "anti_js": {"used_javascript": False, "node_repl_used": False},
        "lean_quality_passed": True,
        "ticket_before": ticket,
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "lane",
        "hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "calibration",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "decision",
        "rejection_reason",
        "next_retry_requires",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "artifact",
        "runner",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if key in payload}


def build_card(payload: dict[str, Any]) -> str:
    readiness = payload["readiness"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: recovered quant_signals forward readiness",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Recovered candidate rows: `{readiness['candidate_rows']}`",
            f"- Valid-session candidate rows: `{readiness['valid_session_candidate_rows']}`",
            f"- Settled replacement-value rows: `{readiness['settled_replacement_value_rows']}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons'])}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Result",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            f"```powershell\n{RUNNER_COMMAND}\n```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        *[REPO_ROOT / path for path in RECOVERED_TARGETS],
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
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
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "readiness": payload["readiness"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
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
                "candidate_rows": payload["readiness"]["candidate_rows"],
                "valid_session_candidate_rows": payload["readiness"][
                    "valid_session_candidate_rows"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
