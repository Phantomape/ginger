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
