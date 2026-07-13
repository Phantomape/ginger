import json

from daily_news_structured_event_snapshot import (
    DAILY_STRUCTURED_OBSERVER_RULE_VERSION,
    build_daily_structured_event_snapshot,
    persist_daily_structured_event_snapshot,
)
from data_paths import daily_artifact_path


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_persist_daily_structured_event_snapshot_writes_artifacts(tmp_path):
    _write_json(
        tmp_path / "daily" / "news" / "trade" / "clean_trade_news_20260629.json",
        [
            {
                "title": "AMD raises guidance",
                "summary": "AMD raises guidance by 12% after strong earnings",
                "published_at": "2026-06-29T13:00:00Z",
                "tickers": ["AMD"],
                "source": "unit",
                "tier": "T1",
                "url": "https://example.test/amd",
            },
            {
                "title": "META announces buyback",
                "summary": "META buyback and capital return plan",
                "published_at": "2026-06-29T13:05:00Z",
                "tickers": ["META"],
                "source": "unit",
            },
        ],
    )

    snapshot = persist_daily_structured_event_snapshot("20260629", data_dir=tmp_path)
    event_path = daily_artifact_path("daily_news_structured_events", "20260629", tmp_path)
    observation_path = daily_artifact_path(
        "daily_news_structured_event_observations",
        "20260629",
        tmp_path,
    )

    assert snapshot["rule_version"] == DAILY_STRUCTURED_OBSERVER_RULE_VERSION
    assert event_path.exists()
    assert observation_path.exists()
    event_payload = json.loads(event_path.read_text(encoding="utf-8"))
    observations = _read_jsonl(observation_path)
    assert event_payload["event_contract_audit"]["ledger_rows"] >= 2
    assert len(observations) == event_payload["event_contract_audit"]["ledger_rows"]
    assert {row["outcome_status"] for row in observations} == {"pending_forward_close"}
    assert {row["entry_date"] for row in observations} == {"2026-06-30"}
    assert {row["entry_date_status"] for row in observations} == {
        "planned_next_session_open"
    }
    assert {row["target_price"] for row in observations} == {None}
    assert {row["target_price_applicability"] for row in observations} == {
        "not_applicable_fixed_horizon_observation"
    }
    assert any(row["target_relation_quality"] is True for row in observations)
    assert any(row["excluded_positive_relation"] is True for row in observations)
    assert event_payload["trade_enabled"] is False
    assert event_payload["strategy_behavior_changed"] is False


def test_daily_structured_event_snapshot_ids_are_stable(tmp_path):
    _write_json(
        tmp_path / "daily" / "news" / "trade" / "clean_trade_news_20260629.json",
        [
            {
                "title": "AMD customer win",
                "summary": "AMD wins $5 billion order with Mega Cloud",
                "published_at": "2026-06-29",
                "tickers": ["AMD"],
            }
        ],
    )

    first = build_daily_structured_event_snapshot("2026-06-29", data_dir=tmp_path)
    second = build_daily_structured_event_snapshot("20260629", data_dir=tmp_path)

    assert [row["event_id"] for row in first["rows"]] == [
        row["event_id"] for row in second["rows"]
    ]
    assert [row["observation_id"] for row in first["forward_observations"]] == [
        row["observation_id"] for row in second["forward_observations"]
    ]


def test_empty_daily_structured_event_snapshot_is_schema_valid(tmp_path):
    _write_json(
        tmp_path / "daily" / "news" / "trade" / "clean_trade_news_20260629.json",
        [],
    )

    snapshot = persist_daily_structured_event_snapshot("20260629", data_dir=tmp_path)
    observation_path = daily_artifact_path(
        "daily_news_structured_event_observations",
        "20260629",
        tmp_path,
    )

    assert snapshot["event_contract_audit"]["ledger_rows"] == 0
    assert snapshot["forward_observation_contract_audit"]["observation_rows"] == 0
    assert observation_path.read_text(encoding="utf-8") == ""
