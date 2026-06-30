import json

from daily_news_text_sanitation import (
    RULE_VERSION,
    audit_daily_news_file,
    build_daily_news_sanitation_audit,
    iter_daily_news_files,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_iter_daily_news_files_uses_final_json_and_counts_temp_files(tmp_path):
    root = tmp_path / "news"
    _write_json(root / "clean" / "clean_news_20260626.json", [])
    _write_json(root / "clean" / ".clean_news_20260627.json.abc.tmp", [])
    _write_json(root / "trade" / "clean_trade_news_20260626.json", [])
    _write_json(root / "trade" / ".clean_trade_news_20260627.json.def.tmp", [])

    rows = iter_daily_news_files(root)

    assert [row["kind"] for row in rows] == ["clean_news", "clean_trade_news"]
    assert {row["news_date"] for row in rows} == {"2026-06-26"}
    assert {row["ignored_temp_files_seen"] for row in rows} == {2}


def test_audit_daily_news_file_records_hashes_without_rewriting_text(tmp_path):
    path = tmp_path / "clean_news_20260626.json"
    _write_json(
        path,
        [
            {
                "title": "AMD&nbsp;wins",
                "summary": "AMD\u200b upgrade confirmed",
                "tickers": ["AMD"],
            },
            {
                "title": "Chip shares rise",
                "summary": "Sector note",
                "tickers": ["NVDA"],
            },
        ],
    )

    audit = audit_daily_news_file(path, kind="clean_news")

    assert audit["summary"]["rule_version"] == RULE_VERSION
    assert audit["rows"] == 2
    assert audit["items"][0]["pre_sanitize_hash"]
    assert audit["items"][0]["field_hashes"]["title_pre_hash"]
    assert "sanitized_text" not in audit["items"][0]
    assert audit["items"][1]["ticker_entity_status"] == "metadata_only"
    assert "ticker_entity_metadata_only" in audit["items"][1]["flags"]


def test_build_daily_news_sanitation_audit_aggregates_flags(tmp_path):
    root = tmp_path / "news"
    _write_json(
        root / "clean" / "clean_news_20260625.json",
        [{"title": "META\u00e2\u0080\u0099s headset", "tickers": ["META"]}],
    )
    _write_json(
        root / "trade" / "clean_trade_news_20260625.json",
        [{"title": "AMD rally", "summary": "AMD wins", "tickers": ["AMD"], "tier": "T1"}],
    )

    audit = build_daily_news_sanitation_audit(root)

    assert audit["file_count"] == 2
    assert audit["items"] == 2
    assert audit["changed_items"] >= 1
    assert audit["flag_counts"]["mojibake_suspect"] == 1
    assert audit["all_hash_fields_present"] is True
    assert audit["date_range"] == {"start": "2026-06-25", "end": "2026-06-25"}
