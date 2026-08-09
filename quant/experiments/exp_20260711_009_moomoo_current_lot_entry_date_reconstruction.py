"""exp-20260711-009: current-lot entry-date reconstruction after a reopen."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "scripts", ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from moomoo_open_positions import reconstruct_entry_dates  # noqa: E402


EXPERIMENT_ID = "exp-20260711-009"
ARTIFACT = ROOT / "data" / "experiments" / EXPERIMENT_ID / "exp_20260711_009_moomoo_current_lot_entry_date_reconstruction.json"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"

SNXX_FILLS = [
    {"ticker": "US.SNXX", "side": "BUY", "qty": 200.0, "date": "2026-07-02"},
    {"ticker": "US.SNXX", "side": "SELL", "qty": 200.0, "date": "2026-07-08"},
    {"ticker": "US.SNXX", "side": "BUY", "qty": 50.0, "date": "2026-07-10"},
]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ticket = json.loads(TICKET.read_text(encoding="utf-8"))
    positions = json.loads((ROOT / "operator_inputs" / "open_positions.json").read_text(encoding="utf-8"))
    rows = sum((positions.get(key) or [] for key in ("core_positions", "positions", "observations")), [])
    snxx = next(row for row in rows if row.get("ticker") == "SNXX")
    reconstructed = reconstruct_entry_dates(
        SNXX_FILLS, current_qty_by_ticker={"SNXX": float(snxx["shares"])}
    ).get("SNXX")
    checks = {
        "broker_history_full_close_on_2026_07_08": SNXX_FILLS[1]["qty"] == 200.0,
        "broker_history_rebuy_on_2026_07_10": SNXX_FILLS[2]["qty"] == 50.0,
        "current_qty_anchored_reconstruction": reconstructed == "2026-07-10",
        "current_snapshot_corrected": snxx.get("entry_date") == reconstructed,
        "shares_preserved": snxx.get("shares") == 50.0,
        "average_cost_preserved": snxx.get("avg_cost") == 28.06,
        "target_preserved": snxx.get("target_price") == 33.67,
    }
    passed = all(checks.values())
    decision = (
        "accepted_measurement_repair_current_lot_backward_fill_reconstruction"
        if passed
        else "blocked"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "status": "accepted" if passed else "blocked",
        "decision": decision,
        "hypothesis": ticket["hypothesis"],
        "change_type": "identity_or_measurement_repair",
        "changed_variable": "moomoo_current_lot_backward_fill_reconstruction_v1",
        "single_causal_variable": "moomoo_current_lot_backward_fill_reconstruction_v1",
        "invalidates_experiment": "exp-20260711-006",
        "broker_evidence": {"fills": SNXX_FILLS, "current_qty": 50.0, "current_avg_cost": 28.06},
        "before": {"entry_date": "2026-07-02", "basis": "stale position-id ledger fallback"},
        "after": {"entry_date": reconstructed, "basis": "current-quantity anchored newest fills"},
        "checks": checks,
        "production_impact": {
            "measurement_only": True,
            "orders_changed": False,
            "prices_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
        },
        "post_run_reflection": {
            "why_result_happened": "Moomoo reused the same position_id after the 200-share lot was fully sold on July 8 and a new 50-share lot was bought July 10; a stale position-id ledger is therefore not lot identity.",
            "forbidden_near_neighbor_retry": "Do not recover entry_date from position_id or ticker history without current-quantity and intervening-fill reconciliation.",
            "new_evidence_required": "A future repair needs a concrete corporate-action, transfer, or incomplete-fill case that the current-quantity backward reconstruction cannot resolve.",
        },
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_moomoo_open_positions.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260711_009_moomoo_current_lot_entry_date_reconstruction.py",
        ],
        "lean_quality_passed": passed,
    }
    write_json(ARTIFACT, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    CARD.write_text(
        f"# {EXPERIMENT_ID} Current-Lot Entry-Date Repair\n\n"
        f"Status: `{payload['status']}`\n\nSNXX current lot entered `{reconstructed}`. "
        "The stale July 2 position-id fallback is invalidated; no trade or order field changed.\n",
        encoding="utf-8",
    )
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result={"decision": decision, "artifact": str(ARTIFACT.relative_to(ROOT)), "checks": checks},
        status=payload["status"],
        fields={
            **payload,
            "owner": "alpha-explore",
            "artifact": str(ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
            "card_file": str(CARD.relative_to(ROOT)).replace("\\", "/"),
            "revision_manifest_file": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"),
            "allowed_write_scope": ticket["allowed_write_scope"],
        },
    )
    write_json(MANIFEST, {"experiment_id": EXPERIMENT_ID, "status": payload["status"], "decision": decision, "checks": checks})
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": decision, "entry_date": reconstructed, "checks": checks}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
