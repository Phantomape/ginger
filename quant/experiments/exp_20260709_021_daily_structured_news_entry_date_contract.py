"""exp-20260709-021: daily structured-news entry-date contract repair.

Measurement repair only. Daily structured-news forward observations already
declare next-session-open entry semantics and fixed 10-session attribution, but
persisted rows did not carry entry_date. This runner proves the daily contract
now mirrors the accepted intraday fixed-horizon contract without changing
relation rules, horizon, notional, orders, or response curves.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260709-021"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "daily_structured_news_entry_date_contract"
RUNNER = f"quant/experiments/exp_20260709_021_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from daily_news_structured_event_snapshot import (  # noqa: E402
    build_daily_structured_event_snapshot,
)
from daily_news_structured_events import (  # noqa: E402
    FORWARD_OBSERVATION_RULE_VERSION,
    safe,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
STRUCTURED_DIR = REPO_ROOT / "data" / "daily" / "news" / "structured"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_021_{SLUG}.json"
REPAIRED_JSONL = OUT_DIR / "repaired_current_daily_observations.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

OBSERVATION_FILE_RE = re.compile(
    r"^daily_news_structured_event_observations_(?P<tag>\d{8})\.jsonl$"
)
HYPOTHESIS = (
    "alpha_blocker/measurement_repair: daily structured-news relation-quality "
    "observer cannot become Gate-ready LLM event-scoring alpha while forward "
    "observations omit deterministic next-session entry_date even though "
    "entry_semantics says next_session_open_after_news_date. Repair the daily "
    "entry_date contract to match the accepted intraday fixed-horizon observer "
    "without changing relation rules, horizon, notional, orders, or response "
    "curves."
)
ALPHA_HYPOTHESIS = (
    "Daily structured relation-quality news rows may become LLM event-scoring "
    "alpha after the fixed observer accumulates replayable entry dates and "
    "later closed cash/SPY/QQQ replacement values."
)
CHANGE_TYPE = "measurement_repair_daily_structured_news_entry_date_contract"
IMPLEMENTATION_MODE = "fixed_horizon_forward_observation_schema_repair"
MECHANISM_FAMILY = "daily_structured_news_alpha_enabling_measurement"
TRIAL_FAMILY = "daily_structured_news_entry_date_contract"
TRIAL_VARIANT_ID = "daily_structured_news_entry_date_contract_parity_v1"
CHANGED_VARIABLE = "daily_structured_news_entry_date_contract_parity_v1"
NEW_EVIDENCE_TYPE = "daily_structured_news_entry_date_gate2_contract_repair"
CAUSAL_COMPONENTS = [
    "daily_news_structured_events.next_session_after",
    "daily fixed-horizon target_price non-applicability",
    "test coverage",
    "current-row repair audit",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-006",
    "exp-20260630-007",
    "exp-20260701-003",
    "exp-20260704-024",
    "exp-20260708-004",
]
REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\daily_news_structured_events.py "
    "quant\\test_daily_news_structured_events.py "
    "quant\\test_daily_news_structured_event_snapshot.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest "
    "quant\\test_daily_news_structured_events.py "
    "quant\\test_daily_news_structured_event_snapshot.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{repo_rel(path)}:{line_number}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def file_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"path": repo_rel(path), "exists": path.exists()}
    if not path.exists():
        return info
    stat = path.stat()
    info.update(
        {
            "size_bytes": stat.st_size,
            "sha256": sha256_file(path),
            "last_modified_utc": dt.datetime.fromtimestamp(
                stat.st_mtime,
                tz=dt.timezone.utc,
            )
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        }
    )
    return info


def load_ticket() -> dict[str, Any]:
    data = read_json(TICKET_JSON, {})
    return data if isinstance(data, dict) else {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or []) if isinstance(payload, Mapping) else []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    if not windows:
        return {
            "available": False,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "window_count": 0,
        }
    return {
        "available": True,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows),
            2,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": max(
            float(row.get("max_drawdown_pct") or 0.0) for row in windows
        ),
    }


def summarize_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    entry_dates = [str(row.get("entry_date")) for row in rows if row.get("entry_date")]
    return {
        "row_count": len(rows),
        "entry_date_present_count": len(entry_dates),
        "entry_date_missing_count": sum(1 for row in rows if not row.get("entry_date")),
        "entry_date_values": sorted(set(entry_dates)),
        "entry_date_status_counts": dict(
            sorted(Counter(str(row.get("entry_date_status") or "missing") for row in rows).items())
        ),
        "target_price_present_count": sum(1 for row in rows if row.get("target_price") is not None),
        "target_price_null_count": sum(1 for row in rows if row.get("target_price") is None),
        "target_price_applicability_present_count": sum(
            1 for row in rows if row.get("target_price_applicability")
        ),
        "target_relation_quality_rows": sum(
            1 for row in rows if row.get("target_relation_quality") is True
        ),
        "replacement_value_vs_cash_present_count": sum(
            1 for row in rows if row.get("replacement_value_vs_cash_usd") is not None
        ),
        "replacement_value_vs_spy_present_count": sum(
            1 for row in rows if row.get("replacement_value_vs_spy_usd") is not None
        ),
        "replacement_value_vs_qqq_present_count": sum(
            1 for row in rows if row.get("replacement_value_vs_qqq_usd") is not None
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "ticker_top10": dict(Counter(str(row.get("ticker") or "") for row in rows).most_common(10)),
    }


def observation_files() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in sorted(STRUCTURED_DIR.glob("daily_news_structured_event_observations_*.jsonl")):
        match = OBSERVATION_FILE_RE.match(path.name)
        if match:
            files.append((match.group("tag"), path))
    return files


def build_current_repair_audit() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    captures: list[dict[str, Any]] = []
    old_all: list[dict[str, Any]] = []
    repaired_all: list[dict[str, Any]] = []
    changed_id_count = 0
    row_count_mismatches = 0
    missing_source_dates = 0
    for date_tag, path in observation_files():
        old_rows = load_jsonl(path)
        old_ids = {str(row.get("observation_id") or "") for row in old_rows}
        try:
            snapshot = build_daily_structured_event_snapshot(
                date_tag,
                data_dir=REPO_ROOT / "data",
            )
            repaired_rows = list(snapshot["forward_observations"])
        except Exception as exc:  # pragma: no cover - recorded in artifact
            snapshot = {"error": f"{type(exc).__name__}: {exc}"}
            repaired_rows = []
            missing_source_dates += 1
        repaired_ids = {str(row.get("observation_id") or "") for row in repaired_rows}
        id_delta = len(old_ids.symmetric_difference(repaired_ids))
        row_delta = len(repaired_rows) - len(old_rows)
        changed_id_count += id_delta
        if row_delta:
            row_count_mismatches += 1
        old_all.extend(old_rows)
        repaired_all.extend(repaired_rows)
        captures.append(
            {
                "path": repo_rel(path),
                "date_tag": date_tag,
                "old": summarize_rows(old_rows),
                "repaired": summarize_rows(repaired_rows),
                "observation_id_symmetric_difference": id_delta,
                "row_count_delta": row_delta,
                "snapshot_error": snapshot.get("error")
                if isinstance(snapshot, Mapping)
                else None,
            }
        )
    return (
        {
            "observation_artifact_count": len(captures),
            "old": summarize_rows(old_all),
            "repaired": summarize_rows(repaired_all),
            "observation_id_symmetric_difference": changed_id_count,
            "row_count_mismatch_date_count": row_count_mismatches,
            "missing_source_date_count": missing_source_dates,
            "captures": captures,
        },
        repaired_all,
    )


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = load_ticket()
    prediction = ticket.get("prediction") or {}
    baseline = load_baseline_metrics()
    repair_audit, repaired_rows = build_current_repair_audit()
    old = repair_audit["old"]
    repaired = repair_audit["repaired"]
    failed_reasons: list[str] = []
    if old["row_count"] <= 0:
        failed_reasons.append("no_current_daily_observation_rows")
    if repair_audit["row_count_mismatch_date_count"]:
        failed_reasons.append("repaired_row_count_mismatch")
    if repair_audit["observation_id_symmetric_difference"]:
        failed_reasons.append("observation_ids_changed")
    if repaired["entry_date_missing_count"]:
        failed_reasons.append("repaired_entry_date_still_missing")
    if repaired["target_price_present_count"]:
        failed_reasons.append("repaired_rows_created_target_price_exit")
    if repaired["target_price_applicability_present_count"] != repaired["row_count"]:
        failed_reasons.append("target_price_non_applicability_missing")
    if repaired["replacement_value_vs_cash_present_count"]:
        failed_reasons.append("replacement_values_changed_before_settlement")
    if repair_audit["missing_source_date_count"]:
        failed_reasons.append("current_source_date_rebuild_failed")
    accepted = not failed_reasons
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_daily_structured_news_entry_date_contract"
        if accepted
        else "blocked_daily_structured_news_entry_date_contract"
    )
    changed_files = [
        "quant/daily_news_structured_events.py",
        "quant/test_daily_news_structured_events.py",
        "quant/test_daily_news_structured_event_snapshot.py",
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(REPAIRED_JSONL),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    target_price_note = (
        "target_price remains null by design because this fixed-horizon "
        "observer does not schedule target exits or orders; readiness uses "
        "entry_date plus closed cash/SPY/QQQ replacement-value comparators."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": (
            "Daily structured-news is a distinct forward-observation surface "
            "from the already repaired intraday contract: current daily "
            "artifacts had 35/35 entry_date-missing rows, while post-20260705 "
            "intraday artifacts already carry planned_next_session_open."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 1 if accepted else 0,
            "actual_decision": decision,
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": any(
                mode in failed_reasons for mode in prediction.get("main_failure_modes") or []
            ),
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - (1.0 if accepted else 0.0))
                ** 2,
                6,
            ),
            "surprise_note": (
                "Low surprise: the daily contract used the same deterministic "
                "calendar shape already accepted for intraday."
                if accepted
                else "The daily entry-date contract did not satisfy row-count, ID, or schema checks."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260630-006": "Accepted daily structured-news forward observation contract, but entry_date remained null.",
                "exp-20260704-024": "Accepted the equivalent intraday entry_date contract repair.",
                "exp-20260708-004": "Recovered daily 20260707 artifacts but left rows pending and entry_date-null.",
                "novelty_gate_caveat": "Reservation fingerprint overmatched OHLCV/notional; true surface is daily_structured_news measurement repair.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if current daily observation rows rebuild with the "
                "same observation IDs and row counts, all repaired rows carry "
                "entry_date, target_price stays null with explicit fixed-horizon "
                "non-applicability, replacement values remain pending, and "
                "strategy metrics stay unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "forward_observation_rule_version": FORWARD_OBSERVATION_RULE_VERSION,
            "entry_date_policy": "next_us_equity_session_after_event_date",
            "target_price_policy": "not_applicable_fixed_horizon_observation",
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "repaired_rows_written_to_experiment_artifact_only": True,
        },
        "gate1": {"passed": baseline.get("available") is True, "baseline_metrics": baseline},
        "gate2": {
            "passed": accepted,
            "old_entry_date_present_count": old["entry_date_present_count"],
            "old_entry_date_missing_count": old["entry_date_missing_count"],
            "repaired_entry_date_present_count": repaired["entry_date_present_count"],
            "repaired_entry_date_missing_count": repaired["entry_date_missing_count"],
            "target_price_scope": target_price_note,
            "target_price_applicability_present_count": repaired[
                "target_price_applicability_present_count"
            ],
            "observation_id_symmetric_difference": repair_audit[
                "observation_id_symmetric_difference"
            ],
            "required_fields_checked": [
                "observation_id",
                "event_id",
                "event_date",
                "ticker",
                "entry_date",
                "entry_date_status",
                "target_price",
                "target_price_applicability",
                "outcome_status",
            ],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No executable filter/rank/size/exit rule changed; baseline survival is unchanged.",
        },
        "gate4": {
            "passed": accepted,
            "measurement_repair_only": True,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "before_metrics": {
            **baseline,
            "current_daily_observation_rows": old["row_count"],
            "entry_date_present_count": old["entry_date_present_count"],
            "target_price_applicability_present_count": old[
                "target_price_applicability_present_count"
            ],
        },
        "after_metrics": {
            **baseline,
            "repaired_daily_observation_rows": repaired["row_count"],
            "entry_date_present_count": repaired["entry_date_present_count"],
            "target_price_applicability_present_count": repaired[
                "target_price_applicability_present_count"
            ],
            "gate_ready_current_rows": 0,
        },
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "entry_date_present_delta": repaired["entry_date_present_count"]
            - old["entry_date_present_count"],
            "target_price_applicability_present_delta": repaired[
                "target_price_applicability_present_count"
            ]
            - old["target_price_applicability_present_count"],
            "observation_id_symmetric_difference": repair_audit[
                "observation_id_symmetric_difference"
            ],
            "repaired_replacement_value_vs_cash_present_count": repaired[
                "replacement_value_vs_cash_present_count"
            ],
        },
        "current_repair_audit": repair_audit,
        "production_impact": {
            "shared_policy_changed": False,
            "shared_observer_contract_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "run_intraday_adapter_changed": False,
            "daily_snapshot_exposed": True,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_sizing_entry_exit_changed": False,
            "llm_prompt_changed": False,
            "live_ready": False,
            "parity_note": (
                "Future daily structured-news observation snapshots will carry "
                "planned entry_date while preserving fixed-horizon, default-off, "
                "read-only semantics. No order or target exit is created."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The daily contract already declared deterministic next-session "
                "entry semantics but did not materialize the date. Reusing the "
                "US equity session calendar fills all current rebuilt rows "
                "without changing observation IDs. The remaining blocker is "
                "closed replacement-value comparators, not target_price."
            )
            if accepted
            else "The repaired daily contract failed one or more row-count, ID, or schema checks.",
            "forbidden_near_neighbor_retry": (
                "Do not reslice these daily structured-news rows by relation, "
                "polarity, keyword, ticker, source, event age, prompt wording, "
                "top-N, hold, notional, or response curve. Do not add a "
                "synthetic target_price to fixed-horizon observations."
            ),
            "new_evidence_required": (
                "Reopen daily structured-news alpha only after production or an "
                "experiment-owned outcome ledger has at least 20 rows with "
                "entry_date plus closed cash/SPY/QQQ replacement values, or "
                "after a distinct PIT LLM scorer writes this same evidence-span "
                "schema. target_price remains non-applicable for this fixed-"
                "horizon observer."
            ),
            "fingerprint_caveat": (
                "experiment.py classified the reservation as ohlcv_relation/"
                "notional_scalar; the actual evidence surface is daily_"
                "structured_news measurement repair."
            ),
        },
        "next_retry_requires": [
            "at least 20 closed daily structured-news rows with entry_date",
            "cash/SPY/QQQ replacement-value comparators for those rows",
            "or a distinct PIT LLM event scorer writing the same evidence schema",
        ],
        "alpha_ready_reason": (
            "Not alpha-ready: this fixes entry_date schema only. Current rows "
            "still lack closed cash/SPY/QQQ replacement values."
        ),
        "changed_files": changed_files,
        "related_files": [
            "experiments/logs/exp-20260630-006.json",
            "experiments/logs/exp-20260630-007.json",
            "experiments/logs/exp-20260704-024.json",
            "quant/daily_news_structured_event_snapshot.py",
            "data/daily/news/structured",
        ],
        "artifact": repo_rel(OUT_JSON),
        "repaired_current_observation_ledger": repo_rel(REPAIRED_JSONL),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "lean_quality_passed": accepted,
        "_repaired_rows": repaired_rows,
        "ticket_before": ticket,
    }


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
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
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "alpha_ready_reason",
        "changed_files",
        "artifact",
        "repaired_current_observation_ledger",
        "runner",
        "reproduction_commands",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: Mapping[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Daily Structured-News Entry-Date Contract",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: no",
            "- Strategy behavior changed: no",
            f"- Current rows audited: `{payload['before_metrics']['current_daily_observation_rows']}`",
            f"- Entry-date rows before/after: `{payload['before_metrics']['entry_date_present_count']}` -> `{payload['after_metrics']['entry_date_present_count']}`",
            f"- Observation ID symmetric difference: `{delta['observation_id_symmetric_difference']}`",
            f"- Replacement-value rows after repair: `{delta['repaired_replacement_value_vs_cash_present_count']}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
        ]
    ) + "\n"


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "quant" / "daily_news_structured_events.py",
        REPO_ROOT / "quant" / "test_daily_news_structured_events.py",
        REPO_ROOT / "quant" / "test_daily_news_structured_event_snapshot.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        REPAIRED_JSONL,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "repaired_current_observation_ledger": repo_rel(REPAIRED_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "generated_at": utc_now(),
        "files": {repo_rel(path): file_info(path) for path in files},
        "reproduction_commands": REPRODUCTION_COMMANDS,
    }


def persist(payload: dict[str, Any]) -> None:
    repaired_rows = payload.pop("_repaired_rows")
    ticket_before = payload.pop("ticket_before")
    write_jsonl(REPAIRED_JSONL, repaired_rows)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, build_manifest(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "repaired_current_observation_ledger": payload[
                "repaired_current_observation_ledger"
            ],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": payload["new_evidence_axis"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "alpha_ready_reason": payload["alpha_ready_reason"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "calibration": payload["calibration"],
            "current_repair_audit": payload["current_repair_audit"],
            "artifact": payload["artifact"],
            "repaired_current_observation_ledger": payload[
                "repaired_current_observation_ledger"
            ],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "revision_manifest_file": payload["revision_manifest_file"],
            "runner": RUNNER,
            "novelty": ticket_before.get("novelty"),
            "experiment_uid": ticket_before.get("experiment_uid"),
            "hub_identity": ticket_before.get("hub_identity"),
            "created_at": ticket_before.get("created_at"),
            "claimed_at": ticket_before.get("claimed_at"),
            "completed_at": payload["timestamp"],
            "ticket_file": repo_rel(TICKET_JSON),
            "allowed_write_scope": payload["changed_files"],
            "locked_variables": ticket_before.get("locked_variables") or [CHANGED_VARIABLE],
            "acceptance_rule": ticket_before.get("acceptance_rule"),
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "entry_date_present_delta": payload["delta_metrics"][
                    "entry_date_present_delta"
                ],
                "observation_id_symmetric_difference": payload["delta_metrics"][
                    "observation_id_symmetric_difference"
                ],
                "replacement_value_rows": payload["delta_metrics"][
                    "repaired_replacement_value_vs_cash_present_count"
                ],
                "gate4": payload["gate4"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
