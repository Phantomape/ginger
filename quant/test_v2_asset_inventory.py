import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "v2" / "v1_asset_inventory.json"
CATEGORIES = {
    "reuse_directly",
    "reuse_after_contract_upgrade",
    "migrate_as_zero_weight_challenger",
    "legacy_diagnostic_only",
    "retire",
}


def _load_inventory() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def test_v1_asset_inventory_contract_and_anchors() -> None:
    inventory = _load_inventory()

    assert inventory["schema_version"] == 1
    assert inventory["record_type"] == "v2_v1_asset_inventory"
    assert set(inventory["classification_enum"]) == CATEGORIES
    assert set(inventory["classification_definitions"]) == CATEGORIES
    assert inventory["global_constraints"]["trade_enabled"] is False
    assert inventory["global_constraints"]["inherits_v1_universe"] is False
    assert inventory["global_constraints"]["inherits_v1_alpha_conclusions"] is False
    assert inventory["global_constraints"]["inherits_v1_weights"] is False
    assert inventory["global_constraints"]["inherits_v1_qualification_or_promotion"] is False
    assert re.fullmatch(r"[0-9a-f]{40}", inventory["source_repository"]["commit"])

    assets = inventory["assets"]
    asset_ids = [asset["asset_id"] for asset in assets]
    assert len(asset_ids) == len(set(asset_ids))

    counts = Counter(asset["classification"] for asset in assets)
    assert set(counts) == CATEGORIES
    assert dict(counts) == inventory["summary"]["classification_counts"]
    assert len(assets) == inventory["summary"]["total_assets"]

    for asset in assets:
        assert asset["classification"] in CATEGORIES
        assert asset["eligible_for_v2_decisions"] is False
        assert asset["trade_enabled"] is False
        assert asset["anchors"]
        assert asset["evidence"].strip()
        assert asset["v2_action"].strip()
        for anchor in asset["anchors"]:
            assert (ROOT / anchor).exists(), f"missing inventory anchor: {anchor}"

    challengers = [
        asset
        for asset in assets
        if asset["classification"] == "migrate_as_zero_weight_challenger"
    ]
    assert challengers
    assert all(asset["initial_weight"] == 0 for asset in challengers)


def test_v1_asset_inventory_does_not_claim_a_passing_v1_audit() -> None:
    inventory = _load_inventory()

    assert inventory["startup_audit"]["command_exit_code"] == 0
    assert inventory["startup_audit"]["audit_passed"] is False
    assert inventory["summary"]["experiment_id_consumed"] is False
    assert inventory["summary"]["production_impact"] == "none"
