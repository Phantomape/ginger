"""Read-only reproduction of Edge's terminal-history counting discrepancy.

The reviewed classifications below are an audit sample, not new experiment
verdicts. Original ticket/log/result/correction bytes remain authoritative.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
EDGE = ROOT / ".codex/worktrees/edge-v2"
sys.path.insert(0, str(EDGE))
from quant.experiment_final_state import apply_final_states
from quant.experiment_history import build_trial_accounting, is_measurement_repair_record

SAMPLE = {
    "measurement": ["20260826-001", "20260826-002", "20260826-003", "20260826-004",
                    "20260826-005", "20260901-002", "20260901-003", "20260906-009",
                    "20260906-010", "20260907-001", "20260907-003", "20260909-001"],
    "valid_rejected": ["20260822-001", "20260901-001", "20260906-003",
                       "20260907-002", "20260907-006", "20260907-007"],
    "valid_insufficient_sample": ["20260902-001"],
    "invalid": ["20260906-004", "20260906-005", "20260906-006", "20260907-004",
                "20260907-005", "20260907-008", "20260907-009", "20260907-010",
                "20260907-011", "20260909-003"],
    "administrative_not_evaluated": ["20260906-007"],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    now = datetime.now(timezone.utc)
    code = [EDGE / "quant/experiment_history.py", EDGE / "quant/experiment_final_state.py"]
    bound = {p: digest(p) for p in code}
    for p in (EDGE / "experiments/dispositions").glob("*.json"):
        bound[p] = digest(p)
    rows, identities = [], []
    for classification, ids in SAMPLE.items():
        for suffix in ids:
            eid = "exp-" + suffix
            tp = EDGE / "experiments/tickets" / f"{eid}.json"
            lp = EDGE / "experiments/logs" / f"{eid}.json"
            ticket = json.loads(tp.read_text(encoding="utf-8-sig"))
            row = json.loads(lp.read_text(encoding="utf-8-sig"))
            assert ticket["status"] in {"accepted", "rejected", "observed_only"}
            if eid == "exp-20260826-001":
                assert ticket["experiment_uid"] == "expuid-83c12a36877a414e"
            rows.append(dict(row, _source=str(lp)))
            bound.update({tp: digest(tp), lp: digest(lp)})
            finished = datetime.fromisoformat(ticket["completed_at"].replace("Z", "+00:00"))
            identities.append({"experiment_id": eid, "experiment_uid": ticket.get("experiment_uid"),
                               "reviewed_classification": classification,
                               "ticket_lane": ticket.get("lane"), "completed_at": ticket["completed_at"],
                               "in_last_24h": now - timedelta(hours=24) <= finished <= now})
    resolved = apply_final_states(rows, EDGE)
    accounting = build_trial_accounting(resolved)
    assert all(digest(p) == expected for p, expected in bound.items()), "Concurrent evidence/code change; retry read-only review."
    output = {
        "review_only": True, "economic_progress": False, "trade_enabled": False,
        "pulse_as_of": now.isoformat(), "source_ref": "refs/heads/automation/edge-v2",
        "sample_scope": "30 already-terminal Edge V2 records since T0; excludes current open work and root namespace",
        "reviewed_counts": {k: len(v) for k, v in SAMPLE.items()},
        "reviewed_valid_trials": 7, "qualified_positive_leads": 0,
        "actual_resolver_valid_trials": sum(r["resolved_final_state"]["valid_alpha_trial"] for r in resolved),
        "actual_history_records_counted": accounting["records_counted"],
        "actual_history_valid_trials": sum(g["valid_alpha_trials"] for g in accounting["groups"]),
        "actual_measurement_classifier_count": sum(is_measurement_repair_record(r) for r in resolved),
        "last_24h_counts": {k: sum(x["in_last_24h"] and x["reviewed_classification"] == k for x in identities) for k in SAMPLE},
        "identities": identities,
        "current_reproduction_hashes": {p.relative_to(ROOT).as_posix(): h for p, h in bound.items()},
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
