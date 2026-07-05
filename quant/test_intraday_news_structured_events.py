import json

from intraday_news_structured_events import (
    ENTRY_SEMANTICS,
    FORWARD_OBSERVATION_RULE_VERSION,
    STRUCTURED_EVENT_RULE_VERSION,
    build_forward_observation_contract,
    build_structured_event_ledger,
    iter_intraday_trade_news_files,
    next_session_after,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_iter_intraday_trade_news_files_parses_capture_and_ignores_temp_files(tmp_path):
    root = tmp_path / "intraday"
    _write_json(root / "news" / ".intraday_trade_news_20260629_1302ET.json.abc.tmp", [])
    _write_json(
        root / "news" / "intraday_trade_news_20260629_1302ET.json",
        [],
    )
    _write_json(
        root / "snapshots" / "intraday_review_20260629_1302ET.json",
        {"generated_at_et": "2026-06-29 13:02 ET"},
    )

    records = iter_intraday_trade_news_files(root)

    assert len(records) == 1
    assert records[0]["capture_date"] == "2026-06-29"
    assert records[0]["time_label"] == "1302ET"
    assert records[0]["snapshot_exists"] is True
    assert records[0]["ignored_temp_files_seen"] == 1


def test_structured_event_ledger_requires_explicit_ticker_and_adds_intraday_provenance(tmp_path):
    root = tmp_path / "intraday"
    _write_json(
        root / "snapshots" / "intraday_review_20260629_1302ET.json",
        {
            "generated_at_et": "2026-06-29 13:02 ET",
            "capture_time_et": "2026-06-29 13:02 ET",
        },
    )
    _write_json(
        root / "news" / "intraday_trade_news_20260629_1302ET.json",
        [
            {
                "title": "AMD raises guidance",
                "summary": "AMD wins $5 billion order with Mega Cloud",
                "published_at": "2026-06-29T15:00:00Z",
                "tickers": ["AMD"],
                "source": "unit",
                "tier": "T1",
                "url": "https://example.test/amd",
            },
            {
                "title": "Chip shares rise",
                "summary": "Sector note without ticker text",
                "published_at": "2026-06-29T15:00:00Z",
                "tickers": ["NVDA"],
                "source": "unit",
            },
        ],
    )

    ledger = build_structured_event_ledger(root, repo_root=tmp_path)
    rows = ledger["rows"]

    assert ledger["rule_version"] == STRUCTURED_EVENT_RULE_VERSION
    assert {row["ticker"] for row in rows} == {"AMD"}
    assert ledger["audit"]["required_field_audit"]["all_required_fields_present"] is True
    assert ledger["audit"]["missing_snapshot_files"] == 0
    assert ledger["audit"]["target_relation_quality_rows"] >= 1
    assert all(row["capture_date"] == "2026-06-29" for row in rows)
    assert all(row["time_label"] == "1302ET" for row in rows)
    assert all(
        row["source_provenance"]["snapshot_path"].startswith("intraday/snapshots/")
        for row in rows
    )


def test_forward_observation_contract_has_intraday_stable_ids_and_pending_outcomes(tmp_path):
    root = tmp_path / "intraday"
    _write_json(
        root / "news" / "intraday_trade_news_20260629_1302ET.json",
        [
            {
                "title": "TSLA rating upgrade",
                "summary": "TSLA rating upgrade after delivery forecast raised by 10%",
                "published_at": "2026-06-29T12:00:00Z",
                "tickers": ["TSLA"],
            }
        ],
    )

    event_rows = build_structured_event_ledger(root, repo_root=tmp_path)["rows"]
    first = build_forward_observation_contract(event_rows)
    second = build_forward_observation_contract(event_rows)

    assert first["rule_version"] == FORWARD_OBSERVATION_RULE_VERSION
    assert first["audit"]["duplicate_observation_ids"] == 0
    assert first["audit"]["required_field_audit"]["all_required_fields_present"] is True
    assert first["rows"][0]["observation_id"] == second["rows"][0]["observation_id"]
    assert first["rows"][0]["entry_semantics"] == ENTRY_SEMANTICS
    assert first["rows"][0]["outcome_status"] == "pending_forward_close"
    assert first["rows"][0]["entry_date"] == "2026-06-30"
    assert first["rows"][0]["entry_date_status"] == "planned_next_session_open"
    assert first["rows"][0]["target_price"] is None
    assert (
        first["rows"][0]["target_price_applicability"]
        == "not_applicable_fixed_horizon_observation"
    )
    assert first["rows"][0]["target_relation_quality"] is True


def test_next_session_after_skips_weekends_and_nyse_holidays():
    assert next_session_after("2026-07-02") == "2026-07-06"
    assert next_session_after("2026-07-03") == "2026-07-06"
    assert next_session_after("2026-07-04") == "2026-07-06"
