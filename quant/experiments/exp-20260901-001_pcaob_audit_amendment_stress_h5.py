"""Evaluate the frozen PCAOB audit-amendment stress scout exactly once.

This runner is research-only. It verifies the claim-bound inputs before reading
the frozen SPY open/close outcomes and can close only as observed_only/rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260901-001"
OWNER = "codex-edge-v2"
SCOUT_DIR = ROOT / "data/v2/scouts/pcaob_audit_amendment_stress_h5_20260901"
TICKET = ROOT / f"experiments/tickets/{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs/experiment_registry.json"
DECISION = SCOUT_DIR / "decision_record.json"
RECIPE = SCOUT_DIR / "evaluation_recipe.json"
CALENDAR = SCOUT_DIR / "warehouse_calendar_preflight.json"
OUT_DIR = ROOT / f"data/experiments/{EXPERIMENT_ID}"
RAW_INPUT = OUT_DIR / "spy_h5_evaluation_input.json"
ARTIFACT = OUT_DIR / "pcaob_audit_amendment_stress_h5_result.json"
RUNNER_REL = (
    "quant/experiments/exp-20260901-001_pcaob_audit_amendment_stress_h5.py"
)
CALENDAR_SQL = (
    "SELECT rowid, ticker, date FROM ohlcv "
    "WHERE ticker=? ORDER BY date, rowid"
)


class ContaminationError(RuntimeError):
    """A frozen identity or declared evaluation degree of freedom drifted."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ContaminationError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _finite_positive(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ContaminationError(f"non-numeric {label}") from exc
    if not math.isfinite(number) or number <= 0:
        raise ContaminationError(f"non-positive/non-finite {label}")
    return number


def _verify_claim_bound_inputs(
    ticket: dict[str, Any], warehouse_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    if ticket.get("experiment_id") != EXPERIMENT_ID:
        raise ContaminationError("ticket experiment identity drifted")
    if ticket.get("status") != "claimed" or ticket.get("owner") != OWNER:
        raise ContaminationError("ticket must be claimed by the frozen owner")
    promotion = ticket.get("alpha_promotion") or {}
    if promotion.get("admission_class") != "research_replay":
        raise ContaminationError("ticket lost research_replay admission")
    if promotion.get("result_ceiling") != "observed_only":
        raise ContaminationError("ticket result ceiling drifted")
    if promotion.get("paper_live_eligible") is not False:
        raise ContaminationError("ticket unexpectedly became paper/live eligible")
    if "trade_enabled_false" not in (ticket.get("locked_variables") or []):
        raise ContaminationError("trade-disabled lock is absent")

    snapshots = {
        row.get("locator"): row.get("sha256")
        for row in (
            (ticket.get("alpha_promotion_claim_receipt") or {}).get(
                "research_artifact_snapshots"
            )
            or []
        )
    }
    required = {
        "data/non_ohlcv/pcaob_form_ap/source/FirmFilings_20260716.zip",
        "data/non_ohlcv/pcaob_form_ap/source_manifest.json",
        "data/v2/scouts/pcaob_audit_amendment_stress_h5_20260901/baseline_measurement.json",
        "data/v2/scouts/pcaob_audit_amendment_stress_h5_20260901/candidate_pool.json",
        "data/v2/scouts/pcaob_audit_amendment_stress_h5_20260901/decision_record.json",
        "data/v2/scouts/pcaob_audit_amendment_stress_h5_20260901/evaluation_recipe.json",
        "data/v2/scouts/pcaob_audit_amendment_stress_h5_20260901/source_disposition_manifest.json",
        "data/v2/scouts/pcaob_audit_amendment_stress_h5_20260901/warehouse_calendar_preflight.json",
    }
    if set(snapshots) != required:
        raise ContaminationError("claim receipt research artifact set drifted")
    identities: dict[str, str] = {}
    for locator in sorted(required):
        actual = _sha256(ROOT / locator)
        if actual != snapshots[locator]:
            raise ContaminationError(f"claim-bound artifact drifted: {locator}")
        identities[locator] = actual

    decision = _read_json(DECISION)
    recipe = _read_json(RECIPE)
    calendar = _read_json(CALENDAR)
    if decision.get("outcome_values_read") is not False:
        raise ContaminationError("decision record is not outcome blind")
    if recipe.get("outcomes_accessed_before_freeze") is not False:
        raise ContaminationError("evaluation recipe is not outcome blind")
    if calendar.get("outcome_values_read") is not False:
        raise ContaminationError("calendar preflight claims outcome access")
    if calendar.get("outcome_columns_read") != []:
        raise ContaminationError("calendar preflight contains outcome columns")
    expected_recipe = {
        "ticker": "SPY",
        "entry_field": "open",
        "exit_field": "close",
        "horizon_sessions": 5,
        "round_trip_cost_bps": 10.0,
        "minimum_evaluable_stress_decisions": 30,
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "trade_enabled": False,
    }
    if any(recipe.get(key) != value for key, value in expected_recipe.items()):
        raise ContaminationError("frozen evaluation recipe drifted")
    if decision.get("stress_rule") != "weekly amendment filing count >= 3":
        raise ContaminationError("stress threshold drifted")
    if decision.get("negative_control_rule") != "weekly amendment filing count == 1":
        raise ContaminationError("negative-control threshold drifted")
    if decision.get("stress_decision_count") != 48:
        raise ContaminationError("stress decision count drifted")
    if decision.get("negative_control_decision_count") != 29:
        raise ContaminationError("negative-control decision count drifted")

    warehouse_identity = recipe.get("warehouse_identity") or {}
    actual_warehouse_sha = _sha256(warehouse_path)
    actual_warehouse_bytes = warehouse_path.stat().st_size
    if actual_warehouse_sha != warehouse_identity.get("sha256"):
        raise ContaminationError("outcome warehouse SHA-256 drifted")
    if actual_warehouse_bytes != warehouse_identity.get("bytes"):
        raise ContaminationError("outcome warehouse byte count drifted")
    if actual_warehouse_sha != calendar.get("warehouse_sha256"):
        raise ContaminationError("calendar/recipe warehouse identity split")
    identities["explicit_outcome_warehouse"] = actual_warehouse_sha
    identities[RUNNER_REL] = _sha256(ROOT / RUNNER_REL)
    return decision, recipe, calendar, identities


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)


def _verify_calendar_identity(
    warehouse_path: Path, calendar: dict[str, Any]
) -> None:
    connection = _connect_read_only(warehouse_path)
    try:
        rows = connection.execute(CALENDAR_SQL, ("SPY",)).fetchall()
    finally:
        connection.close()
    observed = [
        {
            "row_identity": _stable_hash(
                {"rowid": int(rowid), "ticker": str(ticker), "date": str(day)}
            ),
            "ticker": str(ticker),
            "date": str(day),
        }
        for rowid, ticker, day in rows
    ]
    if observed != calendar.get("calendar_rows"):
        raise ContaminationError("date-only calendar identity drifted")


def _frozen_decisions(decision: dict[str, Any]) -> list[dict[str, Any]]:
    allowed = {"amendment_stress", "count_one_negative_control"}
    rows = [
        row
        for row in decision.get("weekly_panel") or []
        if row.get("cohort") in allowed
    ]
    stress = [row for row in rows if row["cohort"] == "amendment_stress"]
    control = [
        row for row in rows if row["cohort"] == "count_one_negative_control"
    ]
    if len(stress) != 48 or len(control) != 29:
        raise ContaminationError("frozen decision population drifted")
    if any(not row.get("entry_session_date") or not row.get("exit_session_date") for row in rows):
        raise ContaminationError("frozen decision has a missing session")
    return rows


def _read_exact_prices(
    warehouse_path: Path, decisions: list[dict[str, Any]]
) -> dict[str, Any]:
    dates = sorted(
        {
            value
            for row in decisions
            for value in (row["entry_session_date"], row["exit_session_date"])
        }
    )
    placeholders = ",".join("?" for _ in dates)
    sql = (
        "SELECT rowid, ticker, date, open, close FROM ohlcv "
        f"WHERE ticker=? AND date IN ({placeholders}) ORDER BY date, rowid"
    )
    connection = _connect_read_only(warehouse_path)
    try:
        rows = connection.execute(sql, ("SPY", *dates)).fetchall()
    finally:
        connection.close()
    if len(rows) != len(dates):
        raise ContaminationError("frozen SPY outcome session is missing or duplicated")
    normalized = [
        {
            "rowid": int(rowid),
            "ticker": str(ticker),
            "date": str(day),
            "open": _finite_positive(open_price, f"SPY {day} open"),
            "close": _finite_positive(close_price, f"SPY {day} close"),
        }
        for rowid, ticker, day, open_price, close_price in rows
    ]
    if [row["date"] for row in normalized] != dates:
        raise ContaminationError("outcome query returned a non-frozen session set")
    payload = {
        "schema_version": 1,
        "record_type": "v2_private_replay_exact_evaluation_input",
        "experiment_id": EXPERIMENT_ID,
        "ticker": "SPY",
        "requested_dates": dates,
        "rows": normalized,
        "queried_at": _now(),
        "trade_enabled": False,
    }
    payload["input_identity"] = _stable_hash(
        {"requested_dates": dates, "rows": normalized}
    )
    return payload


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def evaluate(
    decisions: list[dict[str, Any]], raw: dict[str, Any], *, cost_bps: float
) -> dict[str, Any]:
    price_by_date = {row["date"]: row for row in raw["rows"]}
    cost = cost_bps / 10_000.0
    outcomes: list[dict[str, Any]] = []
    for frozen in decisions:
        entry = price_by_date[frozen["entry_session_date"]]
        exit_row = price_by_date[frozen["exit_session_date"]]
        spy_return = exit_row["close"] / entry["open"] - 1.0
        cash_after_cost_return = -cost
        edge = cash_after_cost_return - spy_return
        outcomes.append(
            {
                "week_start": frozen["week_start"],
                "cohort": frozen["cohort"],
                "amendment_filing_count": frozen["amendment_filing_count"],
                "entry_session_date": frozen["entry_session_date"],
                "exit_session_date": frozen["exit_session_date"],
                "entry_open": entry["open"],
                "exit_close": exit_row["close"],
                "spy_return": spy_return,
                "cash_after_cost_return": cash_after_cost_return,
                "cash_minus_spy_edge": edge,
            }
        )
    stress = [
        row["cash_minus_spy_edge"]
        for row in outcomes
        if row["cohort"] == "amendment_stress"
    ]
    control = [
        row["cash_minus_spy_edge"]
        for row in outcomes
        if row["cohort"] == "count_one_negative_control"
    ]
    stress_mean = _mean(stress)
    control_mean = _mean(control)
    checks = {
        "evaluable_stress_n_gte_30": len(stress) >= 30,
        "stress_mean_edge_positive": stress_mean is not None and stress_mean > 0.0,
        "stress_mean_edge_gt_count_one_control": (
            stress_mean is not None
            and control_mean is not None
            and stress_mean > control_mean
        ),
    }
    if len(stress) < 30:
        diagnostic = "inconclusive_insufficient_sample"
    elif all(checks.values()):
        diagnostic = "positive_replay_lead_not_promoted"
    else:
        diagnostic = "rejected"
    return {
        "diagnostic_disposition": diagnostic,
        "round_trip_cost_bps": cost_bps,
        "stress": {
            "evaluable_count": len(stress),
            "mean_cash_minus_spy_edge": stress_mean,
            "median_cash_minus_spy_edge": median(stress) if stress else None,
            "positive_edge_share": (
                sum(value > 0.0 for value in stress) / len(stress)
                if stress
                else None
            ),
        },
        "count_one_negative_control": {
            "evaluable_count": len(control),
            "mean_cash_minus_spy_edge": control_mean,
            "median_cash_minus_spy_edge": median(control) if control else None,
            "positive_edge_share": (
                sum(value > 0.0 for value in control) / len(control)
                if control
                else None
            ),
        },
        "acceptance_checks": checks,
        "decision_outcomes": outcomes,
    }


def _status_and_disposition(evaluation: dict[str, Any]) -> tuple[str, str, bool]:
    diagnostic = evaluation["diagnostic_disposition"]
    if diagnostic == "positive_replay_lead_not_promoted":
        return "observed_only", diagnostic, False
    return "rejected", diagnostic, diagnostic == "invalid_contaminated"


def _artifact_payload(
    *,
    ticket: dict[str, Any],
    status: str,
    disposition: str,
    evidence_invalid: bool,
    identities: dict[str, str],
    raw: dict[str, Any] | None,
    evaluation: dict[str, Any],
    contamination_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_type": "v2_private_replay_scout_result",
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "status": status,
        "decision": status,
        "disposition": disposition,
        "evidence_invalid": evidence_invalid,
        "hypothesis": ticket["hypothesis"],
        "acceptance_rule": ticket["acceptance_rule"],
        "completed_at": _now(),
        "frozen_input_identities": identities,
        "raw_input_artifact": _relative(RAW_INPUT) if raw is not None else None,
        "raw_input_artifact_sha256": _sha256(RAW_INPUT) if raw is not None else None,
        "raw_input_identity": raw.get("input_identity") if raw is not None else None,
        "evaluation": evaluation,
        "contamination_reason": contamination_reason,
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "production_impact": {
            "research_only": True,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_levels_changed": False,
            "shared_policy_changed": False,
            "trade_enabled": False,
        },
        "post_run_reflection": {
            "failure_mode_audit": ticket["prediction"]["main_failure_modes"],
            "forbidden_near_neighbor_retry": (
                "Do not retune the count threshold, H5 horizon, window, or 10 bps cost "
                "on these outcomes."
            ),
            "new_evidence_required": (
                "An as-published PCAOB vintage or prospectively frozen later filings "
                "under the unchanged rule."
            ),
        },
        "reproduction_command": (
            ".\\.venv\\Scripts\\python.exe -B "
            f"{RUNNER_REL.replace('/', chr(92))} --warehouse-path <explicit-path>"
        ),
        "trade_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warehouse-path", type=Path, required=True)
    args = parser.parse_args()
    ticket = _read_json(TICKET)
    identities: dict[str, str] = {}
    raw: dict[str, Any] | None = None
    contamination_reason: str | None = None
    try:
        decision, recipe, calendar, identities = _verify_claim_bound_inputs(
            ticket, args.warehouse_path
        )
        _verify_calendar_identity(args.warehouse_path, calendar)
        decisions = _frozen_decisions(decision)
        raw = _read_exact_prices(args.warehouse_path, decisions)
        _write_json(RAW_INPUT, raw)
        evaluation = evaluate(
            decisions, raw, cost_bps=float(recipe["round_trip_cost_bps"])
        )
    except ContaminationError as exc:
        contamination_reason = str(exc)
        evaluation = {
            "diagnostic_disposition": "invalid_contaminated",
            "acceptance_checks": {},
            "decision_outcomes": [],
        }
    status, disposition, evidence_invalid = _status_and_disposition(evaluation)
    payload = _artifact_payload(
        ticket=ticket,
        status=status,
        disposition=disposition,
        evidence_invalid=evidence_invalid,
        identities=identities,
        raw=raw,
        evaluation=evaluation,
        contamination_reason=contamination_reason,
    )
    _write_json(ARTIFACT, payload)
    artifact_sha = _sha256(ARTIFACT)
    summary = {
        key: value
        for key, value in evaluation.items()
        if key != "decision_outcomes"
    }
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=ticket["prediction"],
        result={
            "decision": status,
            "artifact": _relative(ARTIFACT),
            "artifact_sha256": artifact_sha,
            "disposition": disposition,
            "summary": summary,
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        status=status,
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": status,
                "disposition": disposition,
                "summary": summary,
                "trade_enabled": False,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
