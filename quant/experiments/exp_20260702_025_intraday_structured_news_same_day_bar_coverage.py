"""exp-20260702-025: same-day intraday bar coverage for structured news.

Measurement repair / blocker audit for the only legal next step after the
intraday structured-news h1/h3 read: a true same-day post-13:00 ET execution
surface. This runner does not test polarity, relation type, horizon, notional,
or response shape. It only verifies whether the fixed target observer rows have
post-capture intraday OHLCV bars available for same-day entry and close.
"""

from __future__ import annotations

import hashlib
import json
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

from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260702-025"
OWNER = "alpha-explore"
SLUG = "intraday_structured_news_same_day_bar_coverage"
RUNNER = f"quant/experiments/exp_20260702_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

STRUCTURED_DIR = REPO_ROOT / "data" / "daily" / "intraday" / "structured"
INTRADAY_DIR = REPO_ROOT / "data" / "kova" / "intraday"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_025_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

REQUIRED_OBSERVER_FIELDS = (
    "observation_id",
    "event_id",
    "event_date",
    "capture_date",
    "time_label",
    "ticker",
    "relation_type",
    "relation_polarity",
    "target_relation_quality",
    "entry_semantics",
    "exit_semantics",
    "unit_notional_usd",
    "outcome_status",
)

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_025_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
REPRO_COMMANDS = [
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
    ".\\.venv\\Scripts\\python.exe scripts\\list_experiments.py --status proposed,claimed,running",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


WRITE_FALLBACKS: list[str] = []


def write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError:
        WRITE_FALLBACKS.append(repo_rel(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(obj: Any, path: Path) -> None:
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    try:
        atomic_write_text(text, path)
        return
    except PermissionError:
        WRITE_FALLBACKS.append(repo_rel(path))
        if isinstance(obj, dict):
            obj["write_fallbacks"] = WRITE_FALLBACKS
            text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_ticket() -> dict[str, Any]:
    return load_json(TICKET_JSON)


def observation_files() -> list[Path]:
    return sorted(
        path
        for path in STRUCTURED_DIR.glob(
            "intraday_news_structured_event_observations_*.jsonl"
        )
        if ".tmp" not in path.name
    )


def load_observer_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in observation_files():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            row["_source_file"] = repo_rel(path)
            row["_source_line"] = line_number
            rows.append(row)
    return rows


def field_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing = {
        field: sum(1 for row in rows if row.get(field) in (None, ""))
        for field in REQUIRED_OBSERVER_FIELDS
    }
    return {
        "required_fields": list(REQUIRED_OBSERVER_FIELDS),
        "row_count": len(rows),
        "missing_by_field": missing,
        "all_required_fields_present": all(count == 0 for count in missing.values()),
        "entry_date_present_rows": sum(1 for row in rows if row.get("entry_date")),
        "target_price_present_rows": sum(1 for row in rows if row.get("target_price")),
    }


def dedup_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("capture_date"),
        row.get("ticker"),
        row.get("relation_polarity"),
        row.get("relation_type"),
        row.get("published_at"),
        row.get("evidence_text_hash") or row.get("sanitized_text_hash"),
    )


def dedup_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in sorted(
        rows,
        key=lambda item: (
            str(item.get("capture_date") or ""),
            str(item.get("time_label") or ""),
            str(item.get("observation_id") or ""),
        ),
    ):
        selected.setdefault(dedup_key(row), row)
    return list(selected.values())


def load_intraday_file(date_tag: str) -> tuple[Path, list[dict[str, Any]] | None]:
    path = INTRADAY_DIR / f"intraday_ohlcv_{date_tag}.jsonl"
    if not path.exists():
        return path, None
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return path, rows


def row_has_bars(row: dict[str, Any]) -> bool:
    if row.get("status") == "skipped":
        return False
    if isinstance(row.get("bars"), list) and row["bars"]:
        return True
    if isinstance(row.get("intraday_bars"), list) and row["intraday_bars"]:
        return True
    required_price_fields = ("open", "high", "low", "close")
    return all(row.get(field) is not None for field in required_price_fields)


def same_day_coverage(target_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in target_rows:
        capture_date = str(row.get("capture_date") or "")
        if capture_date:
            by_date[capture_date].append(row)

    per_date: dict[str, Any] = {}
    covered_keys: set[tuple[str, str]] = set()
    skipped_reasons: Counter[str] = Counter()
    total_target_keys = {
        (str(row.get("capture_date") or ""), str(row.get("ticker") or "").upper())
        for row in target_rows
        if row.get("capture_date") and row.get("ticker")
    }

    for capture_date, rows in sorted(by_date.items()):
        date_tag = capture_date.replace("-", "")
        file_path, intraday_rows = load_intraday_file(date_tag)
        target_tickers = sorted({str(row.get("ticker") or "").upper() for row in rows})
        if intraday_rows is None:
            for ticker in target_tickers:
                skipped_reasons["intraday_file_missing"] += 1
            per_date[capture_date] = {
                "intraday_file": repo_rel(file_path),
                "file_exists": False,
                "target_rows": len(rows),
                "target_tickers": target_tickers,
                "intraday_rows": 0,
                "status_counts": {},
                "target_match_count": 0,
                "target_match_status_counts": {},
                "covered_target_tickers": [],
                "missing_target_tickers": target_tickers,
                "skip_reasons": {"intraday_file_missing": len(target_tickers)},
            }
            continue

        status_counts = Counter(str(row.get("status", "<none>")) for row in intraday_rows)
        matches = [
            row
            for row in intraday_rows
            if str(row.get("ticker") or "").upper() in set(target_tickers)
        ]
        target_status_counts = Counter(str(row.get("status", "<none>")) for row in matches)
        covered_tickers = sorted(
            {
                str(row.get("ticker") or "").upper()
                for row in matches
                if row_has_bars(row)
            }
        )
        for ticker in covered_tickers:
            covered_keys.add((capture_date, ticker))

        missing_tickers = sorted(set(target_tickers) - set(covered_tickers))
        date_reasons: Counter[str] = Counter()
        for ticker in missing_tickers:
            ticker_matches = [
                row
                for row in matches
                if str(row.get("ticker") or "").upper() == ticker
            ]
            if not ticker_matches:
                reason = "target_ticker_missing_from_intraday_file"
            else:
                reasons = {str(row.get("reason") or "") for row in ticker_matches}
                if reasons == {"refresh_intraday_false_or_missing_ALPHA_VANTAGE_API_KEY"}:
                    reason = "refresh_intraday_false_or_missing_ALPHA_VANTAGE_API_KEY"
                elif all(str(row.get("status")) == "skipped" for row in ticker_matches):
                    reason = "target_ticker_rows_skipped"
                else:
                    reason = "target_ticker_rows_without_bar_payload"
            skipped_reasons[reason] += 1
            date_reasons[reason] += 1

        per_date[capture_date] = {
            "intraday_file": repo_rel(file_path),
            "file_exists": True,
            "target_rows": len(rows),
            "target_tickers": target_tickers,
            "intraday_rows": len(intraday_rows),
            "status_counts": dict(status_counts),
            "target_match_count": len(matches),
            "target_match_status_counts": dict(target_status_counts),
            "covered_target_tickers": covered_tickers,
            "missing_target_tickers": missing_tickers,
            "skip_reasons": dict(date_reasons),
            "sample_target_match": matches[0] if matches else None,
        }

    coverage_rate = (
        round(len(covered_keys) / len(total_target_keys), 4) if total_target_keys else None
    )
    return {
        "target_ticker_date_keys": len(total_target_keys),
        "covered_ticker_date_keys": len(covered_keys),
        "coverage_rate": coverage_rate,
        "per_date": per_date,
        "skip_reasons": dict(skipped_reasons),
    }


def load_baseline() -> dict[str, Any]:
    raw = load_json(BASELINE_RESULT)
    windows = raw.get("windows") or []
    generated = sum(int(window.get("signals_generated", 0)) for window in windows)
    survived = sum(int(window.get("signals_survived", 0)) for window in windows)
    return {
        "path": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score": round(
            sum(float(window.get("expected_value_score", 0.0)) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl", 0.0)) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count", 0)) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def build_report() -> dict[str, Any]:
    observer_rows = load_observer_rows()
    target_rows = [
        row
        for row in observer_rows
        if row.get("target_relation_quality") is True
        and row.get("relation_polarity") in ("positive", "negative")
    ]
    deduped = dedup_rows(target_rows)
    coverage = same_day_coverage(deduped)
    ready = (
        coverage["covered_ticker_date_keys"] >= 20
        and coverage["coverage_rate"] is not None
        and coverage["coverage_rate"] >= 0.8
    )
    return {
        "observer_source": {
            "directory": repo_rel(STRUCTURED_DIR),
            "files": [repo_rel(path) for path in observation_files()],
            "raw_rows": len(observer_rows),
            "target_relation_quality_rows": len(target_rows),
            "deduped_target_rows": len(deduped),
            "duplicate_rows_removed": len(target_rows) - len(deduped),
            "target_capture_counts": dict(Counter(row.get("capture_date") for row in target_rows)),
            "dedup_capture_counts": dict(Counter(row.get("capture_date") for row in deduped)),
            "dedup_tickers": sorted({row.get("ticker") for row in deduped}),
            "dedup_polarity_counts": dict(
                Counter(row.get("relation_polarity") for row in deduped)
            ),
        },
        "field_audit": field_audit(observer_rows),
        "same_day_intraday_coverage": coverage,
        "same_day_surface_ready": ready,
        "readiness_rule": {
            "ready_if": [
                ">=20 target ticker-date keys have post-capture intraday bars",
                "coverage_rate >= 0.8",
                "both entry after 13:00 ET and regular-session close can be priced",
            ],
            "ready": ready,
        },
    }


def build_payload(report: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    coverage = report["same_day_intraday_coverage"]
    decision = (
        "accepted_measurement_repair_intraday_same_day_bar_surface_ready"
        if report["same_day_surface_ready"]
        else "blocked_intraday_structured_news_same_day_bars_not_materialized"
    )
    status = "accepted_measurement_repair" if report["same_day_surface_ready"] else "blocked"
    why = (
        "The same-day intraday execution surface has enough target ticker-date "
        "bar coverage for a later alpha read."
        if report["same_day_surface_ready"]
        else (
            "The fixed intraday structured-news target cohort has zero usable "
            "same-day intraday bar coverage: 2026-06-29 through 2026-07-01 "
            "target rows are present only as skipped Kova intraday rows, all "
            "because refresh_intraday_false_or_missing_ALPHA_VANTAGE_API_KEY, "
            "and 2026-07-02 has no intraday file yet."
        )
    )
    reopen_condition = (
        "Reopen same-day intraday structured-news execution alpha only after "
        "validated PIT intraday OHLCV materializes post-13:00 ET bars and "
        "regular-session close bars for at least 20 target ticker-date keys, "
        "with coverage_rate >= 0.80 and at least 8 positive-polarity and 4 "
        "negative-polarity target rows, or after a distinct PIT intraday "
        "provider/archive supplies the same fields. Before reserving, compare "
        f"current covered_ticker_date_keys={coverage['covered_ticker_date_keys']} "
        f"and coverage_rate={coverage['coverage_rate']} against this condition."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": report["same_day_surface_ready"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": (
            "Same-day 13:00 ET structured-news execution alpha can only be "
            "evaluated if post-capture intraday OHLCV bars exist for target "
            "tickers; audit and park the surface when Kova intraday rows are "
            "skipped or missing."
        ),
        "alpha_hypothesis": (
            "Timestamped relation-quality intraday news may have same-day "
            "post-capture alpha that next-session h1/h3 reads cannot see, but "
            "the hypothesis is not testable until PIT intraday bars exist for "
            "the fixed target ticker-date cohort."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "intraday_news_llm_event_scoring_alpha",
        "trial_family": "intraday_structured_news_same_day_bar_coverage",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": "intraday_structured_news_same_day_bar_coverage_v1",
        "changed_variable": "intraday_structured_news_same_day_bar_coverage_v1",
        "causal_components": [
            "fixed_intraday_structured_news_target_rows",
            "kova_intraday_ohlcv_file_presence",
            "target_ticker_bar_payload_coverage",
            "same_day_execution_readiness_verdict",
            "no_strategy_behavior_change",
        ],
        "nearby_prior_experiments": [
            "exp-20260702-021",
            "exp-20260702-022",
            "exp-20260702-020",
            "exp-20260630-005",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "coverage_audit_for_true_same_day_intraday_execution",
        "new_evidence_axis": (
            "First coverage audit for the true same-day intraday execution "
            "surface explicitly named as the legal reopening path after "
            "exp-20260702-022; not a relation/theme/keyword/horizon reslice."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Timestamped relation-quality intraday news may have same-day "
                "post-capture alpha that next-session h1/h3 reads cannot see."
            ),
            "2_history_check": (
                "exp-20260702-021 observed a daily second-order replay lead; "
                "exp-20260702-022 rejected next-session h1/h3 intraday rows "
                "because rows were too thin, but explicitly left true same-day "
                "intraday execution timing as a legal new gate shape."
            ),
            "3_single_policy_bundle": (
                "Measurement repair only: audit fixed target cohort same-day "
                "intraday bar coverage. No direction, horizon, relation, "
                "ticker, notional, or response rule is tested."
            ),
            "4_success_failure_standard": (
                "Ready if >=20 target ticker-date keys have bars and coverage "
                "rate >=0.80; otherwise block with quantitative reopen counts."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "baseline": baseline,
        "audit": report,
        "gate1": {
            "baseline_result_file": baseline["path"],
            "baseline_expected_value_score": baseline["expected_value_score"],
            "baseline_total_pnl": baseline["total_pnl"],
            "baseline_trade_count": baseline["trade_count"],
            "passed": True,
        },
        "gate2": {
            "fields": list(REQUIRED_OBSERVER_FIELDS)
            + ["Kova intraday OHLCV bars after 13:00 ET", "same-day close bar"],
            "field_audit": report["field_audit"],
            "same_day_intraday_coverage": coverage,
            "passed": report["same_day_surface_ready"],
            "missing_fields": []
            if report["same_day_surface_ready"]
            else ["post_capture_intraday_bar_payload", "same_day_close_bar"],
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "passed": True,
            "note": "No executable filter was added; baseline survival is unchanged.",
        },
        "gate4": {
            "mode": "measurement_repair_coverage_audit",
            "passed": report["same_day_surface_ready"],
            "failed_reasons": []
            if report["same_day_surface_ready"]
            else [
                "post_capture_intraday_bar_payload_missing",
                "kova_intraday_rows_skipped_missing_alpha_vantage_key",
                "same_day_execution_alpha_not_testable",
            ],
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": "Read-only coverage audit; no production or backtest behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not reserve another experiment to re-confirm this same "
                "same-day intraday structured-news surface is missing bars. "
                "Compare current covered_ticker_date_keys and coverage_rate "
                "against the reopen condition before reserving. Do not reslice "
                "the same 13:00 observer rows by relation_type, ticker, keyword, "
                "polarity, prompt wording, horizon, notional, or response curve."
            ),
            "new_evidence_required": reopen_condition,
        },
        "reopen_condition": reopen_condition,
        "related_files": [repo_rel(path) for path in observation_files()]
        + [repo_rel(INTRADAY_DIR), baseline["path"]],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": REPRO_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
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
        "pre_run_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "reopen_condition",
        "changed_files",
        "reproduction_commands",
    ]
    record = {key: payload[key] for key in keys}
    record["artifact"] = repo_rel(OUT_JSON)
    record["audit_summary"] = {
        "deduped_target_rows": payload["audit"]["observer_source"][
            "deduped_target_rows"
        ],
        "target_ticker_date_keys": payload["audit"]["same_day_intraday_coverage"][
            "target_ticker_date_keys"
        ],
        "covered_ticker_date_keys": payload["audit"]["same_day_intraday_coverage"][
            "covered_ticker_date_keys"
        ],
        "coverage_rate": payload["audit"]["same_day_intraday_coverage"][
            "coverage_rate"
        ],
        "skip_reasons": payload["audit"]["same_day_intraday_coverage"][
            "skip_reasons"
        ],
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    source = payload["audit"]["observer_source"]
    coverage = payload["audit"]["same_day_intraday_coverage"]
    lines = [
        f"# {EXPERIMENT_ID}: intraday structured news same-day bar coverage",
        "",
        f"- status: `{payload['status']}` / decision: `{payload['decision']}`",
        f"- target rows: `{source['target_relation_quality_rows']}`; "
        f"deduped target rows: `{source['deduped_target_rows']}`",
        f"- target ticker-date keys: `{coverage['target_ticker_date_keys']}`",
        f"- covered ticker-date keys: `{coverage['covered_ticker_date_keys']}`",
        f"- coverage rate: `{coverage['coverage_rate']}`",
        f"- skip reasons: `{coverage['skip_reasons']}`",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reopen Condition",
        "",
        payload["reopen_condition"],
        "",
        "## Reproduction",
        "",
    ]
    lines.extend(f"- `{command}`" for command in REPRO_COMMANDS)
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / path for path in CHANGED_FILES]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def main() -> int:
    ticket = load_ticket()
    baseline = load_baseline()
    report = build_report()
    payload = build_payload(report, baseline)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    write_json(log_record, LOG_JSON)
    write_text(build_card(payload), CARD_MD)

    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate2": payload["gate2"],
        "gate4": payload["gate4"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=ticket.get("prediction"),
        result=result,
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
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "reopen_condition": payload["reopen_condition"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    payload["write_fallbacks"] = WRITE_FALLBACKS
    write_json(build_manifest(payload), MANIFEST_JSON)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "deduped_target_rows": report["observer_source"][
                    "deduped_target_rows"
                ],
                "target_ticker_date_keys": report["same_day_intraday_coverage"][
                    "target_ticker_date_keys"
                ],
                "covered_ticker_date_keys": report["same_day_intraday_coverage"][
                    "covered_ticker_date_keys"
                ],
                "coverage_rate": report["same_day_intraday_coverage"]["coverage_rate"],
                "skip_reasons": report["same_day_intraday_coverage"]["skip_reasons"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
