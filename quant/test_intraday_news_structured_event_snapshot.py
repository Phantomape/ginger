import json

from intraday_news_structured_event_snapshot import (
    INTRADAY_STRUCTURED_OBSERVER_RULE_VERSION,
    build_intraday_structured_event_snapshot,
    intraday_structured_event_artifact_path,
    persist_intraday_structured_event_snapshot,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_intraday_capture(tmp_path, date_tag, time_label, items):
    _write_json(
        tmp_path
        / "daily"
        / "intraday"
        / "news"
        / f"intraday_trade_news_{date_tag}_{time_label}.json",
        items,
    )
    _write_json(
        tmp_path
        / "daily"
        / "intraday"
        / "snapshots"
        / f"intraday_review_{date_tag}_{time_label}.json",
        {
            "generated_at_et": f"{date_tag} {time_label}",
            "capture_time_et": f"{date_tag} {time_label}",
            "date": date_tag,
            "time_label": time_label,
        },
    )


def test_persist_intraday_structured_event_snapshot_writes_artifacts(tmp_path):
    _write_intraday_capture(
        tmp_path,
        "20260629",
        "1300ET",
        [
            {
                "title": "AMD raises guidance",
                "summary": "AMD raises guidance by 12% after strong earnings",
                "published_at": "2026-06-29T17:00:00Z",
                "tickers": ["AMD"],
                "source": "unit",
                "tier": "T1",
                "url": "https://example.test/amd",
            },
            {
                "title": "META announces buyback",
                "summary": "META buyback and capital return plan",
                "published_at": "2026-06-29T17:05:00Z",
                "tickers": ["META"],
                "source": "unit",
            },
        ],
    )
    _write_intraday_capture(
        tmp_path,
        "20260629",
        "1400ET",
        [
            {
                "title": "NVDA customer order",
                "summary": "NVDA wins $5 billion order with Mega Cloud",
                "published_at": "2026-06-29T18:00:00Z",
                "tickers": ["NVDA"],
            }
        ],
    )

    snapshot = persist_intraday_structured_event_snapshot(
        "20260629",
        "1300ET",
        data_dir=tmp_path,
    )
    event_path = intraday_structured_event_artifact_path(
        "events",
        "20260629",
        "1300ET",
        tmp_path,
    )
    observation_path = intraday_structured_event_artifact_path(
        "observations",
        "20260629",
        "1300ET",
        tmp_path,
    )

    assert snapshot["rule_version"] == INTRADAY_STRUCTURED_OBSERVER_RULE_VERSION
    assert event_path.exists()
    assert observation_path.exists()
    event_payload = json.loads(event_path.read_text(encoding="utf-8"))
    observations = _read_jsonl(observation_path)
    assert event_payload["event_contract_audit"]["selected_ledger_rows"] >= 2
    assert len(observations) == event_payload["event_contract_audit"]["selected_ledger_rows"]
    assert {row["time_label"] for row in event_payload["rows"]} == {"1300ET"}
    assert {row["time_label"] for row in observations} == {"1300ET"}
    assert "NVDA" not in {row["ticker"] for row in event_payload["rows"]}
    assert {row["outcome_status"] for row in observations} == {"pending_forward_close"}
    assert any(row["target_relation_quality"] is True for row in observations)
    assert {row["entry_date"] for row in observations} == {"2026-06-30"}
    assert {row["entry_date_status"] for row in observations} == {
        "planned_next_session_open"
    }
    assert all(row["target_price"] is None for row in observations)
    assert {row["target_price_applicability"] for row in observations} == {
        "not_applicable_fixed_horizon_observation"
    }
    assert event_payload["trade_enabled"] is False
    assert event_payload["strategy_behavior_changed"] is False


def test_intraday_structured_event_snapshot_ids_are_stable(tmp_path):
    _write_intraday_capture(
        tmp_path,
        "20260629",
        "1300ET",
        [
            {
                "title": "AMD customer win",
                "summary": "AMD wins $5 billion order with Mega Cloud",
                "published_at": "2026-06-29",
                "tickers": ["AMD"],
            }
        ],
    )

    first = build_intraday_structured_event_snapshot(
        "2026-06-29",
        "1300ET",
        data_dir=tmp_path,
    )
    second = build_intraday_structured_event_snapshot(
        "20260629",
        "1300ET",
        data_dir=tmp_path,
    )

    assert [row["event_id"] for row in first["rows"]] == [
        row["event_id"] for row in second["rows"]
    ]
    assert [row["observation_id"] for row in first["forward_observations"]] == [
        row["observation_id"] for row in second["forward_observations"]
    ]


def test_empty_intraday_structured_event_snapshot_is_schema_valid(tmp_path):
    snapshot = persist_intraday_structured_event_snapshot(
        "20260629",
        "1300ET",
        data_dir=tmp_path,
    )
    observation_path = intraday_structured_event_artifact_path(
        "observations",
        "20260629",
        "1300ET",
        tmp_path,
    )

    assert snapshot["event_contract_audit"]["selected_ledger_rows"] == 0
    assert snapshot["forward_observation_contract_audit"]["observation_rows"] == 0
    assert observation_path.read_text(encoding="utf-8") == ""
