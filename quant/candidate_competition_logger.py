"""Append-only pilot competition decision logging.

The key invariant is that counterfactuals are written before entry and outcomes
are appended later against the frozen decision_id. This prevents after-the-fact
selection of a convenient displaced ticker.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECISION_LOG = REPO_ROOT / "data" / "pilot_competition_decisions.jsonl"

REQUIRED_DECISION_FIELDS = {
    "decision_id",
    "timestamp",
    "sleeve",
    "pilot_ticker",
    "action",
    "protocol_version",
    "ranking_snapshot",
    "counterfactuals",
    "risk_snapshot",
}


def stable_decision_hash(snapshot: dict) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def validate_decision_snapshot(snapshot: dict) -> list[str]:
    issues = []
    missing = sorted(REQUIRED_DECISION_FIELDS - set(snapshot))
    if missing:
        issues.append(f"missing fields {missing}")

    if not isinstance(snapshot.get("ranking_snapshot"), list) or not snapshot.get(
        "ranking_snapshot"
    ):
        issues.append("ranking_snapshot must be a non-empty list")

    counterfactuals = snapshot.get("counterfactuals")
    if not isinstance(counterfactuals, list) or not counterfactuals:
        issues.append("counterfactuals must be a non-empty list")
    else:
        total_weight = 0.0
        for idx, item in enumerate(counterfactuals):
            if "type" not in item:
                issues.append(f"counterfactuals[{idx}] missing type")
            if "ticker" not in item:
                issues.append(f"counterfactuals[{idx}] missing ticker")
            weight = item.get("shadow_weight")
            if not isinstance(weight, (int, float)) or weight < 0:
                issues.append(
                    f"counterfactuals[{idx}] shadow_weight must be non-negative"
                )
            else:
                total_weight += float(weight)
        if round(total_weight, 6) <= 0:
            issues.append("counterfactual shadow weights must sum above zero")

    if not isinstance(snapshot.get("risk_snapshot"), dict):
        issues.append("risk_snapshot must be an object")

    return issues


def append_decision_snapshot(
    snapshot: dict,
    path: Path | str = DEFAULT_DECISION_LOG,
) -> str:
    issues = validate_decision_snapshot(snapshot)
    if issues:
        raise ValueError("; ".join(issues))

    record = dict(snapshot)
    record["record_type"] = "decision_snapshot"
    record.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
    record["decision_hash"] = stable_decision_hash(snapshot)

    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record["decision_hash"]


def append_decision_outcome(
    decision_id: str,
    outcome: dict,
    path: Path | str = DEFAULT_DECISION_LOG,
) -> None:
    record = {
        "record_type": "decision_outcome",
        "decision_id": decision_id,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
    }
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def load_decision_log(path: Path | str = DEFAULT_DECISION_LOG) -> list[dict]:
    """Load append-only pilot competition records."""
    log_path = Path(path)
    if not log_path.exists():
        return []

    records = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                records.append(
                    {
                        "record_type": "parse_error",
                        "line_no": line_no,
                        "error": str(exc),
                    }
                )
    return records


def _num(value):
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _planned_risk(payload: dict) -> float | None:
    explicit = _num(payload.get("planned_risk"))
    if explicit is not None:
        return explicit
    entry = _num(payload.get("entry_price"))
    stop = _num(payload.get("stop_price"))
    shares = _num(payload.get("shares"))
    if entry is not None and stop is not None and shares is not None and entry > stop:
        return round((entry - stop) * shares, 6)
    return None


def _pilot_trade_payload(outcome: dict) -> dict:
    trade = outcome.get("pilot_trade")
    if isinstance(trade, dict):
        return trade
    return outcome


def _counterfactual_key(item: dict) -> tuple[str | None, str | None]:
    return (item.get("type"), item.get("ticker"))


def compute_decision_outcome_attribution(
    snapshot: dict | None,
    outcome: dict,
) -> dict:
    """Compute direct and replacement-relative outcome metrics for one decision."""
    pilot_trade = _pilot_trade_payload(outcome)
    pilot_pnl = _num(outcome.get("pilot_pnl"))
    if pilot_pnl is None:
        pilot_pnl = _num(pilot_trade.get("profit_loss"))
    if pilot_pnl is None:
        pilot_pnl = 0.0

    pilot_risk = _num(outcome.get("pilot_risk"))
    if pilot_risk is None:
        pilot_risk = _planned_risk(pilot_trade)

    explicit_cf = outcome.get("counterfactual_outcomes") or []
    explicit_by_key = {
        _counterfactual_key(item): item
        for item in explicit_cf
        if isinstance(item, dict)
    }

    counterfactuals = []
    if snapshot and isinstance(snapshot.get("counterfactuals"), list):
        counterfactuals = snapshot["counterfactuals"]
    elif explicit_cf:
        counterfactuals = explicit_cf

    weighted_replacement_pnl = 0.0
    weighted_replacement_risk = 0.0
    known_weight = 0.0
    required_weight = 0.0
    counterfactual_details = []

    for cf in counterfactuals:
        if not isinstance(cf, dict):
            continue
        weight = _num(cf.get("shadow_weight"))
        if weight is None or weight <= 0:
            continue
        required_weight += weight
        detail = dict(cf)
        explicit = explicit_by_key.get(_counterfactual_key(cf), {})

        if cf.get("ticker") == "CASH":
            cf_pnl = 0.0
            cf_risk = 0.0
            status = "known_cash"
        else:
            cf_pnl = _num(explicit.get("profit_loss"))
            if cf_pnl is None:
                cf_pnl = _num(explicit.get("pnl"))
            cf_risk = _num(explicit.get("planned_risk"))
            if cf_risk is None:
                cf_risk = _planned_risk(explicit)
            status = "known" if cf_pnl is not None else "missing_outcome"

        if cf_pnl is not None:
            weighted_replacement_pnl += weight * cf_pnl
            known_weight += weight
        if cf_risk is not None:
            weighted_replacement_risk += weight * cf_risk

        detail.update(
            {
                "known_status": status,
                "profit_loss": cf_pnl,
                "planned_risk": cf_risk,
            }
        )
        counterfactual_details.append(detail)

    coverage = (known_weight / required_weight) if required_weight > 0 else 0.0
    replacement_complete = required_weight > 0 and round(coverage, 6) >= 1.0
    replacement_value = (
        round(pilot_pnl - weighted_replacement_pnl, 2)
        if replacement_complete
        else None
    )

    risk_adjusted_value = None
    if (
        replacement_complete
        and pilot_risk is not None
        and pilot_risk > 0
        and weighted_replacement_risk > 0
    ):
        risk_adjusted_value = risk_adjusted_replacement_value(
            pilot_pnl,
            weighted_replacement_pnl,
            pilot_risk,
            weighted_replacement_risk,
        )

    return {
        "decision_id": outcome.get("decision_id"),
        "pilot_ticker": (
            pilot_trade.get("ticker")
            or outcome.get("pilot_ticker")
            or (snapshot or {}).get("pilot_ticker")
        ),
        "sleeve": outcome.get("sleeve") or (snapshot or {}).get("sleeve"),
        "pilot_pnl": round(pilot_pnl, 2),
        "pilot_risk": round(pilot_risk, 6) if pilot_risk is not None else None,
        "cash_relative_pnl": round(pilot_pnl, 2),
        "replacement_pnl": (
            round(weighted_replacement_pnl, 2) if replacement_complete else None
        ),
        "replacement_value": replacement_value,
        "risk_adjusted_replacement_value": risk_adjusted_value,
        "counterfactual_coverage": round(coverage, 4),
        "replacement_value_status": (
            "complete" if replacement_complete else "pending_counterfactual_outcomes"
        ),
        "counterfactuals": counterfactual_details,
    }


def summarize_pilot_competition(
    path: Path | str = DEFAULT_DECISION_LOG,
    *,
    sleeve: str | None = None,
) -> dict:
    """Aggregate pilot direct PnL and replacement-value evidence."""
    records = load_decision_log(path)
    snapshots = {
        record.get("decision_id"): record
        for record in records
        if record.get("record_type") == "decision_snapshot"
    }
    outcome_records = [
        record for record in records if record.get("record_type") == "decision_outcome"
    ]

    attributions = []
    for record in outcome_records:
        decision_id = record.get("decision_id")
        outcome = dict(record.get("outcome") or {})
        outcome["decision_id"] = decision_id
        snapshot = snapshots.get(decision_id)
        if sleeve and (outcome.get("sleeve") or (snapshot or {}).get("sleeve")) != sleeve:
            continue
        attribution = compute_decision_outcome_attribution(snapshot, outcome)
        attribution["logged_at"] = record.get("logged_at")
        attribution["has_snapshot"] = snapshot is not None
        attributions.append(attribution)

    complete = [
        item for item in attributions
        if item.get("replacement_value_status") == "complete"
    ]
    risk_adjusted = [
        item["risk_adjusted_replacement_value"]
        for item in complete
        if item.get("risk_adjusted_replacement_value") is not None
    ]

    by_ticker = {}
    for item in attributions:
        ticker = item.get("pilot_ticker") or "UNKNOWN"
        bucket = by_ticker.setdefault(
            ticker,
            {
                "outcomes": 0,
                "direct_pilot_pnl": 0.0,
                "cash_relative_pnl": 0.0,
                "complete_replacement_outcomes": 0,
                "replacement_value": 0.0,
                "risk_adjusted_replacement_value_sum": 0.0,
                "risk_adjusted_replacement_value_count": 0,
            },
        )
        bucket["outcomes"] += 1
        bucket["direct_pilot_pnl"] += item.get("pilot_pnl") or 0.0
        bucket["cash_relative_pnl"] += item.get("cash_relative_pnl") or 0.0
        if item.get("replacement_value_status") == "complete":
            bucket["complete_replacement_outcomes"] += 1
            bucket["replacement_value"] += item.get("replacement_value") or 0.0
        if item.get("risk_adjusted_replacement_value") is not None:
            bucket["risk_adjusted_replacement_value_sum"] += item[
                "risk_adjusted_replacement_value"
            ]
            bucket["risk_adjusted_replacement_value_count"] += 1

    for bucket in by_ticker.values():
        bucket["direct_pilot_pnl"] = round(bucket["direct_pilot_pnl"], 2)
        bucket["cash_relative_pnl"] = round(bucket["cash_relative_pnl"], 2)
        bucket["replacement_value"] = round(bucket["replacement_value"], 2)
        count = bucket["risk_adjusted_replacement_value_count"]
        bucket["risk_adjusted_replacement_value_avg"] = (
            round(bucket["risk_adjusted_replacement_value_sum"] / count, 6)
            if count
            else None
        )
        bucket.pop("risk_adjusted_replacement_value_sum", None)

    replacement_value_sum = round(
        sum(item.get("replacement_value") or 0.0 for item in complete),
        2,
    )
    direct_pnl_sum = round(sum(item.get("pilot_pnl") or 0.0 for item in attributions), 2)

    return {
        "decision_snapshots": len(snapshots),
        "outcome_records": len(attributions),
        "direct_pilot_pnl": direct_pnl_sum,
        "cash_relative_pnl": direct_pnl_sum,
        "complete_replacement_outcomes": len(complete),
        "pending_replacement_outcomes": len(attributions) - len(complete),
        "replacement_value": replacement_value_sum if complete else None,
        "risk_adjusted_replacement_value_avg": (
            round(sum(risk_adjusted) / len(risk_adjusted), 6)
            if risk_adjusted
            else None
        ),
        "by_ticker": by_ticker,
        "latest_outcomes": attributions[-5:],
        "note": (
            "No pilot outcomes logged yet."
            if not attributions
            else "Replacement value is complete only when all frozen counterfactual outcomes are known."
        ),
    }


def risk_adjusted_replacement_value(
    pilot_pnl: float,
    replacement_pnl: float,
    pilot_risk: float,
    replacement_risk: float,
) -> float:
    """Compare PnL per unit risk for pilot vs. displaced alternative."""
    if pilot_risk <= 0 or replacement_risk <= 0:
        raise ValueError("pilot_risk and replacement_risk must be positive")
    return round((pilot_pnl / pilot_risk) - (replacement_pnl / replacement_risk), 6)
