from __future__ import annotations

import json
from copy import deepcopy

import remote.server as server


def _auth_headers() -> dict[str, str]:
    return {"X-Remote-Token": server.SECRET}


def _sample_payload() -> dict:
    return {
        "as_of": "2026-05-15",
        "account": "test",
        "portfolio_value_usd": 100000,
        "cash_usd": None,
        "observations": [],
        "positions": [
            {
                "ticker": "MSFT",
                "direction": "long",
                "shares": 2,
                "avg_cost": 410.25,
                "entry_date": "2026-05-01",
                "target_price": 460.5,
                "stop_price": 390.0,
                "opened_by_strategy": "manual",
                "risk_notes": "test row",
            }
        ],
    }


def _configure_tmp_open_positions(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server, "OPEN_POSITIONS_FILE", tmp_path / "open_positions.json")
    monkeypatch.setattr(server, "LOG_DIR", tmp_path / "logs")
    server.OPEN_POSITIONS_FILE.write_text(
        json.dumps(_sample_payload(), indent=4) + "\n",
        encoding="utf-8",
    )
    server.app.config.update(TESTING=True)


def test_open_positions_get_and_put_writes_backup_and_audit(monkeypatch, tmp_path) -> None:
    _configure_tmp_open_positions(monkeypatch, tmp_path)
    client = server.app.test_client()

    get_response = client.get("/open-positions", headers=_auth_headers())
    assert get_response.status_code == 200
    loaded = get_response.get_json()
    assert loaded["field_audit"]["passed"] is True

    payload = loaded["payload"]
    payload["positions"][0]["target_price"] = "475.25"
    put_response = client.put("/open-positions", json=payload, headers=_auth_headers())

    assert put_response.status_code == 200
    saved = json.loads(server.OPEN_POSITIONS_FILE.read_text(encoding="utf-8"))
    assert saved["positions"][0]["target_price"] == 475.25
    assert list((tmp_path / "logs" / "open_positions_backups").glob("open_positions_*.json"))
    audit_lines = (tmp_path / "logs" / "open_positions_edits.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"replace_payload"' in line for line in audit_lines)


def test_open_positions_put_rejects_missing_gate2_fields(monkeypatch, tmp_path) -> None:
    _configure_tmp_open_positions(monkeypatch, tmp_path)
    client = server.app.test_client()
    invalid = deepcopy(_sample_payload())
    invalid["positions"][0].pop("target_price")

    response = client.put("/open-positions", json=invalid, headers=_auth_headers())

    assert response.status_code == 400
    assert "positions[0].target_price is required" in response.get_json()["errors"]
    saved = json.loads(server.OPEN_POSITIONS_FILE.read_text(encoding="utf-8"))
    assert saved["positions"][0]["target_price"] == 460.5


def test_patch_single_open_position(monkeypatch, tmp_path) -> None:
    _configure_tmp_open_positions(monkeypatch, tmp_path)
    client = server.app.test_client()

    response = client.patch(
        "/open-positions/positions/MSFT",
        json={"shares": "3.5", "risk_notes": "updated"},
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["position"]["shares"] == 3.5
    assert payload["position"]["risk_notes"] == "updated"
    saved = json.loads(server.OPEN_POSITIONS_FILE.read_text(encoding="utf-8"))
    assert saved["positions"][0]["shares"] == 3.5
