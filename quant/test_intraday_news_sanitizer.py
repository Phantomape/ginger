"""Tests for replayable intraday news text sanitation metadata."""

from news_text_sanitizer import (
    annotate_news_item,
    annotate_news_items,
    build_news_sanitation_summary,
    sanitize_text,
)


def test_sanitize_text_flags_mojibake_cjk_in_latin_title():
    audit = sanitize_text("Why Meta should win but isn\u9225\u6a9bt")

    assert audit["status"] == "suspect"
    assert "mojibake_suspect" in audit["flags"]
    assert audit["pre_sanitize_hash"]
    assert audit["post_sanitize_hash"]


def test_sanitize_text_strips_hidden_control_and_unescapes_html():
    audit = sanitize_text("AMD\u200b upgrade&nbsp;confirmed")

    assert audit["status"] == "suspect"
    assert "hidden_or_control_char" in audit["flags"]
    assert "html_entity_unescaped" in audit["flags"]
    assert audit["sanitized_text"] == "AMD upgrade confirmed"


def test_annotate_news_item_preserves_original_fields_and_ticker_match():
    item = {
        "title": "AMD upgrade",
        "summary": "Analyst raises AMD target",
        "tickers": ["AMD"],
    }
    annotated = annotate_news_item(item, watched_tickers=["AMD", "NVDA"])

    assert annotated["title"] == item["title"]
    audit = annotated["text_sanitation"]
    assert audit["status"] == "ok"
    assert audit["ticker_entity_match"]["status"] == "explicit_text_match"
    assert audit["watched_ticker_overlap"] == ["AMD"]


def test_metadata_only_ticker_match_is_audited_as_prompt_risk():
    annotated = annotate_news_item(
        {"title": "Chip shares rise", "summary": "Sector note", "tickers": ["NVDA"]}
    )

    audit = annotated["text_sanitation"]
    assert audit["status"] == "suspect"
    assert "ticker_entity_metadata_only" in audit["flags"]
    assert audit["ticker_entity_match"]["status"] == "metadata_only"


def test_summary_counts_statuses_and_flags():
    items = annotate_news_items(
        [
            {"title": "AMD upgrade", "summary": "AMD wins", "tickers": ["AMD"]},
            {"title": "Why Meta isn\u9225\u6a9bt loved", "tickers": ["META"]},
        ]
    )
    summary = build_news_sanitation_summary(items)

    assert summary["items"] == 2
    assert summary["flagged_items"] == 1
    assert summary["flag_counts"]["mojibake_suspect"] == 1
    assert summary["status_counts"]["suspect"] == 1
