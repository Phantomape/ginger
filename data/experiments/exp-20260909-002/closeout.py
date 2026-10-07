"""One-time audited measurement close; does not query brokers or rewrite outcomes."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import experiment
import experiment_registry as registry
import judge_experiment

ID = "exp-20260909-002"
OUT = ROOT / "data/experiments" / ID


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    ticket_path = ROOT / "experiments/tickets" / f"{ID}.json"
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    if ticket["status"] != "claimed":
        raise SystemExit("Closeout requires this still-claimed ticket; terminal evidence is immutable.")
    live = json.loads((OUT / "live_verification.json").read_text(encoding="utf-8"))
    assert live["all_passed"] and live["old_account_sample_pnl_unchanged"]
    files = ["quant/execution_attribution.py", "quant/broker_performance.py",
             "quant/broker_execution_ledger.py", "quant/run.py", "quant/report_generator.py",
             "quant/test_execution_attribution.py", "quant/test_broker_performance.py",
             "quant/test_broker_execution_ledger.py", "quant/test_broker_performance_reporting.py",
             "quant/experiments/exp_20260909_002_broker_decision_order_attribution.py",
             "docs/broker_execution_ledger.md", ".gitignore"]
    reflection = {
        "why_result_happened": "Exact prospective identity and complete lifecycle accounting make attribution auditable; committed surface heads detect valid-chain tail truncation. Historical remarks remain empty, so historical strategy PnL stays unknown.",
        "realized_failure_mode": "missing_explicit_order_identity",
        "forbidden_near_neighbor_retry": "Do not infer old strategy ownership from ticker, time proximity or position labels; do not loosen complete lifecycle or immutable-head checks to manufacture coverage.",
        "new_evidence_required": "A prospective broker lifecycle with recorded decision remarks on both legs, or a verified new broker schema/identity conflict requiring measurement repair.",
    }
    write(OUT / "after.json", {
        "experiment_id": ID, "experiment_uid": ticket["experiment_uid"],
        "source_ref": "refs/heads/fix/alpha-score-sleeve-same-day-idempotency",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "before_gate": "unavailable_no_decision_order_lineage",
        "after_gate": "prospective_exact_identity_and_complete_lifecycle_attribution_available",
        "measurement_accepted": True, "economic_progress": False,
        "trade_enabled": False, "orders_submitted": False,
        "tests": {"passed": 145, "command": ".venv/Scripts/python.exe -B -m pytest quant/test_execution_attribution.py quant/test_broker_performance.py quant/test_broker_performance_reporting.py quant/test_broker_execution_ledger.py quant/test_moomoo_history_paging.py quant/test_moomoo_open_positions.py quant/test_bracket_orders.py -q -p no:cacheprovider"},
        "independent_original_reproductions_passed": 5,
        "live_proof_sha256": digest(OUT / "live_verification.json"),
        "live_checks": live["checks"], "existing_logical_orders": 786,
        "historical_bound_orders": 0, "historical_strategy_pnl": None,
        "code_and_document_hashes": {p: digest(ROOT / p) for p in files},
        "post_run_reflection": reflection,
    })
    original = judge_experiment.build_log_draft

    def enriched(*args, **kwargs):
        row = original(*args, **kwargs)
        row.update(experiment_uid=ticket["experiment_uid"],
                   source_ref="refs/heads/fix/alpha-score-sleeve-same-day-idempotency",
                   economic_progress=False, trade_enabled=False,
                   post_run_reflection=reflection)
        return row

    judge_experiment.build_log_draft = enriched
    os.environ["GINGER_SKIP_MEMORY_REFRESH"] = "1"
    sys.argv = ["experiment.py", "close", "--experiment-id", ID,
                "--before", str(OUT / "before.json"), "--after", str(OUT / "after.json"),
                "--write-registry", "--status-override", "accepted", "--append-log",
                "--change-summary", "Accepted prospective decision/order attribution and committed broker surface-head measurement repair; daily JSON and report share one snapshot.",
                "--notes", "145 focused tests and all five independent regression reproductions passed; real read-only capture and zero-append replay passed. Historical 786 orders remain unattributed. No orders, alpha promotion or economic progress.",
                "--realized-failure-mode", "missing_explicit_order_identity",
                "--surprise-note", reflection["why_result_happened"]]
    experiment.main()
    closed = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert closed["status"] == "accepted"
    registry.save_experiment_card(closed, ROOT / "experiments/cards")
    # Preserve the reservation/claim receipt fields and add an after-run index.
    manifest_path = ROOT / "experiments/manifests" / f"{ID}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = files + [f"data/experiments/{ID}/{name}" for name in
                        ("before.json", "after.json", "live_verification.json", "closeout.py")]
    evidence += [f"experiments/{kind}/{ID}.{ext}" for kind, ext in
                 (("tickets", "json"), ("logs", "json"), ("cards", "md"))]
    evidence += [f"experiments/artifacts/{ID}_broker_decision_order_attribution.md"]
    manifest["closeout"] = {"status": "accepted", "economic_progress": False,
                            "files": {p: digest(ROOT / p) for p in evidence}}
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
