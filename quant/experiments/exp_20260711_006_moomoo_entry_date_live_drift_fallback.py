"""exp-20260711-006: prove the moomoo entry-date ledger fallback repair."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "scripts", ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from moomoo_open_positions import load_live_drift_entry_dates  # noqa: E402


EXPERIMENT_ID = "exp-20260711-006"
ARTIFACT = ROOT / "data" / "experiments" / EXPERIMENT_ID / "exp_20260711_006_moomoo_entry_date_live_drift_fallback.json"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ticket = json.loads(TICKET.read_text(encoding="utf-8"))
    positions = json.loads((ROOT / "operator_inputs" / "open_positions.json").read_text(encoding="utf-8"))
    rows = sum((positions.get(key) or [] for key in ("core_positions", "positions", "observations")), [])
    snxx = next(row for row in rows if row.get("ticker") == "SNXX")
    fallbacks = load_live_drift_entry_dates()
    recovered = (fallbacks.get("by_position_id") or {}).get(str(snxx.get("position_id")))
    checks = {
        "ledger_position_id_recovers_entry_date": recovered == "2026-07-02",
        "current_snapshot_entry_date_repaired": snxx.get("entry_date") == recovered,
        "target_price_preserved": snxx.get("target_price") == 33.67,
        "shares_preserved": snxx.get("shares") == 50.0,
        "average_cost_preserved": snxx.get("avg_cost") == 28.06,
    }
    passed = all(checks.values())
    decision = "accepted_measurement_repair_moomoo_entry_date_live_drift_fallback" if passed else "blocked"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "status": "accepted" if passed else "blocked",
        "decision": decision,
        "hypothesis": ticket["hypothesis"],
        "change_type": "identity_or_measurement_repair",
        "changed_variable": "moomoo_entry_date_live_drift_fallback_v1",
        "single_causal_variable": "moomoo_entry_date_live_drift_fallback_v1",
        "before": {"ticker": "SNXX", "entry_date": None},
        "after": {"ticker": "SNXX", "entry_date": snxx.get("entry_date")},
        "checks": checks,
        "production_impact": {
            "measurement_only": True,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_levels_changed": False,
            "trade_enabled": False,
        },
        "post_run_reflection": {
            "why_result_happened": "The broker position survived in the append-only live-drift ledger even though the immediately prior position snapshot omitted the ticker and recent fill reconstruction returned no date.",
            "forbidden_near_neighbor_retry": "Do not infer broker entry dates from nearest historical prices when a position-id ledger fact exists.",
            "new_evidence_required": "Future failures should inspect deal-history enum normalization or a genuinely missing position-id history, not add another fallback source.",
        },
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_moomoo_open_positions.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260711_006_moomoo_entry_date_live_drift_fallback.py",
        ],
        "lean_quality_passed": passed,
    }
    write_json(ARTIFACT, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    CARD.write_text(
        f"# {EXPERIMENT_ID} Moomoo Entry-Date Repair\n\nStatus: `{payload['status']}`\n\n"
        f"SNXX entry_date recovered by position id: `{snxx.get('entry_date')}`. "
        "No quantities, prices, levels, sizing, or orders changed.\n",
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
    write_json(
        MANIFEST,
        {"experiment_id": EXPERIMENT_ID, "status": payload["status"], "decision": decision, "checks": checks},
    )
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": decision, "checks": checks}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
