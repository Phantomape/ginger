import json

from daily_news_structured_events import (
    FORWARD_OBSERVATION_RULE_VERSION,
    STRUCTURED_EVENT_RULE_VERSION,
    build_forward_observation_contract,
    build_structured_event_ledger,
    is_target_relation_quality,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_structured_event_ledger_requires_explicit_ticker_and_ignores_temp_files(tmp_path):
    root = tmp_path / "news"
    _write_json(root / "trade" / ".clean_trade_news_20260627.json.abc.tmp", [])
    _write_json(
        root / "trade" / "clean_trade_news_20260626.json",
        [
            {
                "title": "AMD revenue beats estimates",
                "summary": "AMD wins $5 billion order with Mega Cloud",
                "published_at": "2026-06-26T13:00:00Z",
                "tickers": ["AMD"],
                "source": "unit",
                "tier": "T1",
                "url": "https://example.test/amd",
            },
            {
                "title": "Chip shares rally",
                "summary": "Sector note without ticker text",
                "published_at": "2026-06-26T13:00:00Z",
                "tickers": ["NVDA"],
                "source": "unit",
            },
        ],
    )

    ledger = build_structured_event_ledger(root, repo_root=tmp_path)
    rows = ledger["rows"]

    assert ledger["rule_version"] == STRUCTURED_EVENT_RULE_VERSION
    assert ledger["audit"]["ignored_temp_file_count"] == 1
    assert {row["ticker"] for row in rows} == {"AMD"}
    assert ledger["audit"]["required_field_audit"]["all_required_fields_present"] is True
    assert ledger["audit"]["target_relation_quality_rows"] >= 1
    assert any(row["magnitude"]["has_numeric_magnitude"] for row in rows)
    assert all(row["source_provenance"]["path"].startswith("news/trade/") for row in rows)


def test_target_relation_quality_excludes_capital_return(tmp_path):
    root = tmp_path / "news"
    _write_json(
        root / "trade" / "clean_trade_news_20260626.json",
        [
            {
                "title": "META announces buyback",
                "summary": "META buyback and capital return plan",
                "published_at": "2026-06-26",
                "tickers": ["META"],
            },
            {
                "title": "AMD raises guidance",
                "summary": "AMD raises outlook after strong earnings",
                "published_at": "2026-06-26",
                "tickers": ["AMD"],
            },
        ],
    )

    rows = build_structured_event_ledger(root, repo_root=tmp_path)["rows"]
    by_relation = {row["relation_type"]: row for row in rows}

    assert is_target_relation_quality(by_relation["capital_return"]) is False
    assert is_target_relation_quality(by_relation["guidance_or_rating_upgrade"]) is True


def test_forward_observation_contract_has_stable_ids_and_pending_outcomes(tmp_path):
    root = tmp_path / "news"
    _write_json(
        root / "trade" / "clean_trade_news_20260626.json",
        [
            {
                "title": "AMD guidance upgrade",
                "summary": "AMD raises guidance by 12%",
                "published_at": "2026-06-26",
                "tickers": ["AMD"],
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
    assert first["rows"][0]["outcome_status"] == "pending_forward_close"
    assert first["rows"][0]["entry_date"] is None
    assert first["rows"][0]["target_relation_quality"] is True
