import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "data" / "v2" / "v1_bias_register.json"
INVENTORY = ROOT / "data" / "v2" / "v1_asset_inventory.json"
REQUIRED_BIASES = {
    "v1-static-survivorship-universe",
    "v1-performance-derived-weight-transfer",
    "v1-incomplete-winner-only-selection-panel",
    "v1-mutable-current-state-replacement-value",
    "v1-process-wall-clock-decision-dates",
    "v1-ai-free-text-execution-authority",
}
SEVERITIES = {"critical", "high"}
STATUSES = {"open", "released"}
OPERATORS = {"eq", "gte", "lte"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v1_bias_register_contract_and_anchors() -> None:
    register = _load(REGISTER)
    inventory = _load(INVENTORY)

    assert register["schema_version"] == 1
    assert register["record_type"] == "v2_v1_bias_register"
    assert set(register["severity_enum"]) == SEVERITIES
    assert set(register["status_enum"]) == STATUSES
    assert set(register["release_operator_enum"]) == OPERATORS
    assert re.fullmatch(r"[0-9a-f]{40}", register["source_repository"]["commit"])

    constraints = register["global_constraints"]
    assert constraints["trade_enabled"] is False
    assert constraints["eligible_for_v2_decisions"] is False
    assert constraints["inherits_v1_universe"] is False
    assert constraints["inherits_v1_weights"] is False
    assert constraints["inherits_v1_qualification_or_promotion"] is False
    assert constraints["t0_confirmed"] is False
    assert constraints["release_requires_all_conditions_met"] is True
    assert constraints["bias_release_does_not_enable_trading"] is True

    inventory_ids = {asset["asset_id"] for asset in inventory["assets"]}
    biases = register["biases"]
    bias_ids = [bias["bias_id"] for bias in biases]
    assert len(bias_ids) == len(set(bias_ids))
    assert REQUIRED_BIASES <= set(bias_ids)

    for bias in biases:
        assert bias["severity"] in SEVERITIES
        assert bias["status"] in STATUSES
        assert bias["status"] == "open"
        assert bias["eligible_for_v2_decisions"] is False
        assert bias["trade_enabled"] is False
        assert bias["evidence_anchors"]
        assert bias["related_inventory_asset_ids"]
        assert set(bias["related_inventory_asset_ids"]) <= inventory_ids
        assert bias["evidence"].strip()
        assert bias["blocked_scopes"]
        assert bias["v2_mitigation"].strip()
        assert bias["release_conditions"]
        for anchor in bias["evidence_anchors"]:
            assert (ROOT / anchor).exists(), f"missing bias anchor: {anchor}"
        for condition in bias["release_conditions"]:
            assert condition["condition_id"].strip()
            assert condition["metric"].strip()
            assert condition["operator"] in OPERATORS
            assert isinstance(condition["threshold"], (int, float, bool))
            assert condition["unit"].strip()
            assert condition["evidence_required"].strip()
            assert condition["met"] is False

    counts = Counter(bias["severity"] for bias in biases)
    summary = register["summary"]
    assert len(biases) == summary["total_biases"]
    assert sum(bias["status"] == "open" for bias in biases) == summary["open_biases"]
    assert dict(counts) == summary["severity_counts"]


def test_v1_bias_register_keeps_v1_evidence_blocked_and_default_off() -> None:
    register = _load(REGISTER)

    assert register["startup_audit"]["command_exit_code"] == 0
    assert register["startup_audit"]["audit_passed"] is False
    assert register["startup_audit"]["invalid_alpha_promotion_count"] == 10
    assert register["startup_audit"]["research_result_ceiling_violation_count"] == 1
    assert register["summary"]["experiment_id_consumed"] is False
    assert register["summary"]["production_impact"] == "none"
    assert register["summary"]["parity_impact"] == "classification_only_no_runtime_or_policy_change"
