import json
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
T0_PATH = ROOT / "data" / "v2" / "t0.json"


def test_t0_is_confirmed_without_retroactive_evidence_upgrade() -> None:
    declaration = json.loads(T0_PATH.read_text(encoding="utf-8"))

    assert declaration["schema_version"] == 1
    assert declaration["record_type"] == "v2_t0_declaration"
    assert declaration["declaration_status"] == "confirmed"
    assert declaration["confirmed_by"] == "user"
    assert declaration["t0_date"] == "2026-08-18"
    assert declaration["t0_timezone"] == "America/Los_Angeles"
    assert declaration["t0_date_basis"] == "calendar_date_only_no_invented_intraday_timestamp"
    assert date.fromisoformat(declaration["t0_date"]) <= date.fromisoformat(
        declaration["confirmation_local_date"]
    )
    assert datetime.fromisoformat(declaration["confirmed_at"].replace("Z", "+00:00"))

    policy = declaration["evidence_policy"]
    assert policy["before_user_confirmation"]["canonical_forward_eligible"] is False
    assert (
        policy["after_user_confirmation_before_m1_contracts"]["canonical_forward_eligible"]
        is False
    )
    assert policy["retroactive_evidence_upgrade"] is False
    assert policy["canonical_forward_eligibility_started_at"] is None


def test_t0_confirmation_does_not_enable_trading() -> None:
    declaration = json.loads(T0_PATH.read_text(encoding="utf-8"))

    assert declaration["m0_status"] == "completed"
    assert declaration["experiment_id"] is None
    assert declaration["trade_enabled"] is False
    assert declaration["production_impact"] == "none"
