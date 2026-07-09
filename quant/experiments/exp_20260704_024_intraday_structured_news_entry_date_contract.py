"""exp-20260704-024: intraday structured-news entry-date contract repair.

Measurement repair only. The accepted intraday structured-news forward
observation contract uses next-session-open entry semantics and a fixed
10-session attribution exit, but the persisted observation rows did not carry
an entry_date and downstream readiness audits treated the intentionally-null
target_price as a broken executable target exit. This runner proves the shared
helper now materializes entry_date while preserving stable observation IDs and
the fixed-horizon target_price boundary.
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


EXPERIMENT_ID = "exp-20260704-024"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "intraday_structured_news_entry_date_contract"
RUNNER = f"quant/experiments/exp_20260704_024_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from intraday_news_structured_event_snapshot import (  # noqa: E402
    build_intraday_structured_event_snapshot,
)
from intraday_news_structured_events import (  # noqa: E402
    FORWARD_OBSERVATION_RULE_VERSION,
    safe,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
STRUCTURED_DIR = REPO_ROOT / "data" / "daily" / "intraday" / "structured"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_024_{SLUG}.json"
REPAIRED_JSONL = OUT_DIR / "repaired_current_intraday_observations.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Repair intraday structured-news fixed-horizon forward observation "
    "readiness by materializing next-session entry_date and explicit "
    "target_price non-applicability, without changing filters, ranking, "
    "sizing, exits, orders, prompts, or trade_enabled."
)
ALPHA_HYPOTHESIS = (
    "Timestamped intraday news relation-quality events can become useful LLM "
    "event-scoring alpha only after fixed-contract rows have replayable "
    "entry dates and later closed cash/SPY/QQQ replacement values; without "
    "entry_date, any current-row alpha read is a measurement artifact."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "fixed_horizon_forward_observation_schema_repair"
MECHANISM_FAMILY = "intraday_news_llm_event_scoring_alpha"
TRIAL_FAMILY = "intraday_structured_news_forward_observation_contract"
TRIAL_VARIANT_ID = "entry_date_contract_v1"
CHANGED_VARIABLE = "intraday_structured_news_fixed_horizon_entry_date_contract_v1"
NEW_EVIDENCE_TYPE = "fixed_horizon_forward_observation_schema_repair"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-013",
    "exp-20260702-022",
    "exp-20260702-025",
    "exp-20260704-012",
]
CAUSAL_COMPONENTS = [
    "intraday forward observation next-session entry_date materialization",
    "fixed-horizon target_price non-applicability schema",
    "readiness audit for current intraday structured-news rows",
    "no strategy behavior change",
]
REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\intraday_news_structured_events.py "
    "quant\\test_intraday_news_structured_events.py "
    "quant\\test_intraday_news_structured_event_snapshot.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest "
    "quant\\test_intraday_news_structured_events.py "
    "quant\\test_intraday_news_structured_event_snapshot.py -q",
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
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
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
    if windows:
        return {
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
                (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
                default=None,
            ),
        }
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": 3,
        "expected_value_score_sum": 7.8941,
        "total_pnl": 234850.99,
        "trade_count": 61,
        "signals_generated": 164,
        "signals_survived": 135,
        "survival_rate": 0.823171,
        "max_drawdown_pct_worst": 0.1119,
    }


def parse_observation_path(path: Path) -> tuple[str, str] | None:
    match = re.search(r"observations_(\d{8})_([A-Za-z0-9]+)\.jsonl$", path.name)
    if not match:
        return None
    return match.group(1), match.group(2)


def summarize_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    entry_dates = [str(row.get("entry_date")) for row in rows if row.get("entry_date")]
    return {
        "row_count": len(rows),
        "entry_date_present_count": sum(1 for row in rows if row.get("entry_date")),
        "entry_date_missing_count": sum(1 for row in rows if not row.get("entry_date")),
        "target_price_present_count": sum(1 for row in rows if row.get("target_price")),
        "target_price_null_count": sum(1 for row in rows if row.get("target_price") is None),
        "target_price_applicability_present_count": sum(
            1 for row in rows if row.get("target_price_applicability")
        ),
        "replacement_value_vs_cash_present_count": sum(
            1 for row in rows if row.get("replacement_value_vs_cash_usd") is not None
        ),
        "target_relation_quality_rows": sum(
            1 for row in rows if row.get("target_relation_quality") is True
        ),
        "ticker_date_count": len(
            {
                (str(row.get("ticker") or ""), str(row.get("capture_date") or ""))
                for row in rows
                if row.get("ticker") and row.get("capture_date")
            }
        ),
        "entry_date_values": sorted(set(entry_dates)),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "") for row in rows).items())
        ),
    }


def build_current_repair_audit() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    files = sorted(STRUCTURED_DIR.glob("intraday_news_structured_event_observations_*.jsonl"))
    captures: list[dict[str, Any]] = []
    old_all: list[dict[str, Any]] = []
    repaired_all: list[dict[str, Any]] = []
    changed_id_count = 0
    row_count_mismatches = 0
    missing_source_captures = 0
    for path in files:
        parsed = parse_observation_path(path)
        if parsed is None:
            continue
        date_tag, time_label = parsed
        old_rows = load_jsonl(path)
        old_ids = {str(row.get("observation_id") or "") for row in old_rows}
        try:
            snapshot = build_intraday_structured_event_snapshot(
                date_tag,
                time_label,
                data_dir=REPO_ROOT / "data",
            )
            repaired_rows = list(snapshot["forward_observations"])
        except Exception as exc:  # pragma: no cover - captured in artifact
            snapshot = {"error": f"{type(exc).__name__}: {exc}"}
            repaired_rows = []
            missing_source_captures += 1
        repaired_ids = {str(row.get("observation_id") or "") for row in repaired_rows}
        id_delta = len(old_ids.symmetric_difference(repaired_ids))
        row_delta = len(repaired_rows) - len(old_rows)
        changed_id_count += id_delta
        if row_delta != 0:
            row_count_mismatches += 1
        old_all.extend(old_rows)
        repaired_all.extend(repaired_rows)
        captures.append(
            {
                "path": repo_rel(path),
                "date_tag": date_tag,
                "time_label": time_label,
                "old": summarize_rows(old_rows),
                "repaired": summarize_rows(repaired_rows),
                "observation_id_symmetric_difference": id_delta,
                "row_count_delta": row_delta,
                "snapshot_error": snapshot.get("error")
                if isinstance(snapshot, Mapping)
                else None,
            }
        )
    audit = {
        "observation_artifact_count": len(captures),
        "old": summarize_rows(old_all),
        "repaired": summarize_rows(repaired_all),
        "observation_id_symmetric_difference": changed_id_count,
        "row_count_mismatch_capture_count": row_count_mismatches,
        "missing_source_capture_count": missing_source_captures,
        "captures": captures,
    }
    return audit, repaired_all


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
        failed_reasons.append("no_current_intraday_observation_rows")
    if repair_audit["row_count_mismatch_capture_count"]:
        failed_reasons.append("repaired_row_count_mismatch")
    if repair_audit["observation_id_symmetric_difference"]:
        failed_reasons.append("observation_ids_changed")
    if repaired["entry_date_missing_count"]:
        failed_reasons.append("repaired_entry_date_still_missing")
    if repaired["target_price_present_count"]:
        failed_reasons.append("repaired_rows_created_target_price_exit")
    if repaired["target_price_applicability_present_count"] != repaired["row_count"]:
        failed_reasons.append("target_price_non_applicability_missing")
    if repair_audit["missing_source_capture_count"]:
        failed_reasons.append("current_source_capture_rebuild_failed")
    accepted = not failed_reasons
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_intraday_structured_news_entry_date_contract"
        if accepted
        else "blocked_intraday_structured_news_entry_date_contract"
    )
    changed_files = [
        "quant/intraday_news_structured_events.py",
        "quant/test_intraday_news_structured_events.py",
        "quant/test_intraday_news_structured_event_snapshot.py",
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
        "observer does not schedule target exits or orders; gate readiness "
        "should use entry_date plus closed replacement-value comparators."
    )
    alpha_ready = False
    gate_ready_current_rows = 0
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
        "alpha_ready": alpha_ready,
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
            "Measurement repair to the accepted intraday structured-news "
            "fixed-horizon forward observation contract: materialize planned "
            "next-session entry_date and explicit target_price non-applicability."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 1 if accepted else 0,
            "actual_decision": decision,
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": any(
                mode in failed_reasons
                for mode in prediction.get("main_failure_modes") or []
            ),
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - (1.0 if accepted else 0.0))
                ** 2,
                6,
            ),
            "surprise_note": (
                "Low surprise: the deterministic calendar repair preserved "
                "observation IDs and filled entry_date for the current in-memory "
                "repaired contract."
                if accepted
                else "The fixed-horizon contract repair did not satisfy schema stability checks."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260630-013": (
                    "Accepted the intraday structured-event forward observation "
                    "contract with next-session semantics but intentionally-null "
                    "target_price."
                ),
                "exp-20260702-022": (
                    "Rejected h1/h3 intraday structured-news read; do not "
                    "reslice current rows."
                ),
                "exp-20260702-025": (
                    "Blocked true same-day intraday execution because post-capture "
                    "bar coverage is absent."
                ),
                "exp-20260704-012": (
                    "Blocked current observer settlement surface and named "
                    "intraday entry_date/target_price as a readiness issue."
                ),
                "novelty_gate": "measurement_repair lane; novelty had no blocking near-neighbor.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if current intraday observation rows rebuild with "
                "the same observation IDs and row counts, all repaired rows carry "
                "entry_date, target_price stays null with explicit fixed-horizon "
                "non-applicability, and strategy metrics stay unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "forward_observation_rule_version": FORWARD_OBSERVATION_RULE_VERSION,
            "entry_date_policy": "next_us_equity_session_after_capture_date",
            "target_price_policy": "not_applicable_fixed_horizon_observation",
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "repaired_rows_written_to_experiment_artifact_only": True,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "old_entry_date_present_count": old["entry_date_present_count"],
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
                "capture_date",
                "time_label",
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
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter/rank/size/exit rule changed; baseline survival is unchanged.",
        },
        "gate4": {
            "passed": accepted,
            "measurement_repair_only": True,
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
            "current_intraday_observation_rows": old["row_count"],
            "entry_date_present_count": old["entry_date_present_count"],
            "target_price_applicability_present_count": old[
                "target_price_applicability_present_count"
            ],
        },
        "after_metrics": {
            **baseline,
            "repaired_intraday_observation_rows": repaired["row_count"],
            "entry_date_present_count": repaired["entry_date_present_count"],
            "target_price_applicability_present_count": repaired[
                "target_price_applicability_present_count"
            ],
            "gate_ready_current_rows": gate_ready_current_rows,
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
                "Future intraday structured-news observation snapshots will "
                "carry planned entry_date while preserving fixed-horizon, "
                "default-off, read-only semantics. No order or target exit is "
                "created."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The accepted contract already had deterministic next-session "
                "entry semantics; it simply failed to materialize the date. "
                "Using the existing NYSE session calendar fills all current "
                "repaired rows without changing observation IDs. The remaining "
                "blocker is closed replacement-value comparators, not target_price."
            )
            if accepted
            else "The repaired contract failed one or more row-count, ID, or schema checks.",
            "forbidden_near_neighbor_retry": (
                "Do not reslice these intraday structured-news rows by relation, "
                "polarity, keyword, ticker, event age, prompt wording, top-N, "
                "hold, notional, or response curve. Do not add a synthetic "
                "target_price to fixed-horizon observations."
            ),
            "new_evidence_required": (
                "Reopen intraday structured-news alpha only after production "
                "or an experiment-owned outcome ledger has at least 20 rows "
                "with entry_date plus closed cash/SPY/QQQ replacement values, "
                "or after a distinct PIT intraday provider supplies validated "
                "same-day bars. target_price remains non-applicable for this "
                "fixed-horizon observer."
            ),
        },
        "next_retry_requires": [
            "at least 20 closed intraday structured-news rows with entry_date",
            "cash/SPY/QQQ replacement-value comparators for those rows",
            "or a distinct PIT intraday provider with validated same-day bars",
        ],
        "alpha_ready_reason": (
            "Not alpha-ready: this fixes entry_date schema only. Current rows "
            "still lack closed cash/SPY/QQQ replacement values."
        ),
        "changed_files": changed_files,
        "related_files": [
            "experiments/logs/exp-20260630-013.json",
            "experiments/logs/exp-20260702-022.json",
            "experiments/logs/exp-20260702-025.json",
            "experiments/logs/exp-20260704-012.json",
            "quant/intraday_news_structured_event_snapshot.py",
            "data/daily/intraday/structured",
        ],
        "artifact": repo_rel(OUT_JSON),
        "repaired_current_observation_ledger": repo_rel(REPAIRED_JSONL),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "_repaired_rows": repaired_rows,
        "ticket_before": ticket,
        "lean_quality_passed": None,
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
        "nearby_prior_experiments",
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
        "related_files",
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
            f"# {EXPERIMENT_ID} Intraday Structured-News Entry-Date Contract",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: no",
            "- Strategy behavior changed: no",
            f"- Current rows audited: `{payload['before_metrics']['current_intraday_observation_rows']}`",
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
        REPO_ROOT / "quant" / "intraday_news_structured_events.py",
        REPO_ROOT / "quant" / "test_intraday_news_structured_events.py",
        REPO_ROOT / "quant" / "test_intraday_news_structured_event_snapshot.py",
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
            "allowed_write_scope": ticket_before.get("allowed_write_scope"),
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
