import hashlib
import json
from pathlib import Path
import sys


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from entity_theme_news_event_forward_observer import (  # noqa: E402
    TARGET_PRICE_STATUS,
    exact_url_decision_id,
    persist_entity_theme_news_event_forward_observer,
)


def _daily_dir(root: Path) -> Path:
    path = root / "non_ohlcv" / "entity_theme_news_observer" / "daily"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _item(url: str, published_at: str, tickers=None) -> dict:
    return {
        "url": url,
        "title": f"headline for {url}",
        "published_at": published_at,
        "entity_theme_query_id": "private_space_launch_contracts",
        "primary_entity": "SpaceX",
        "theme": "private_space_contracts",
        "relation_type": "private_entity_to_public_space_exposure",
        "candidate_tickers": tickers
        or ["RKLB", "LUNR", "ASTS", "BA", "LMT", "NOC"],
    }


def _write_daily(root: Path, tag: str, rows: list[dict]) -> Path:
    path = _daily_dir(root) / f"entity_theme_news_observer_{tag}.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _ledger_rows(summary: dict) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(summary["ledger_path"])
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def _bars(dates: list[str], start: float, final_close: float) -> list[dict]:
    return [
        {
            "Date": day,
            "Open": start,
            "High": max(start, final_close if index == len(dates) - 1 else start),
            "Low": min(start, final_close if index == len(dates) - 1 else start),
            "Close": final_close if index == len(dates) - 1 else start,
        }
        for index, day in enumerate(dates)
    ]


def test_latest_daily_emits_ten_exact_url_events_sixty_legs_and_reruns_zero(
    tmp_path,
):
    prior_url = "https://news.example.test/already-seen?exact=1"
    _write_daily(
        tmp_path,
        "20260711",
        [_item(prior_url, "2026-07-11T18:00:00Z")],
    )
    fresh = [
        _item(
            f"https://news.example.test/fresh/{index}?oc=5",
            "2026-07-13T00:00:00Z",
        )
        for index in range(10)
    ]
    _write_daily(
        tmp_path,
        "20260712",
        [
            _item(prior_url, "2026-07-13T01:00:00Z"),
            _item("https://news.example.test/stale", "2026-07-09T00:00:00Z"),
            *fresh,
        ],
    )

    first = persist_entity_theme_news_event_forward_observer(
        "20260713",
        observed_at="2026-07-13T06:45:17Z",
        data_dir=tmp_path,
        ohlcv_by_ticker={},
    )

    assert first["status"] == "ok"
    assert first["decision_count"] == 10
    assert first["leg_count"] == 60
    assert first["rows_appended"] == 60
    assert first["settled_count"] == 0
    assert first["trade_enabled"] is False
    assert first["strategy_behavior_changed"] is False
    assert first["availability_timestamp_field"] == "first_seen_at"
    assert first["published_at_role"] == "freshness_metadata_only_not_availability"
    assert first["skipped_counts"]["already_seen"] == 1
    assert first["skipped_counts"]["outside_freshness_window"] == 1
    assert all(
        round(sum(leg["paper_notional_usd"] for leg in event["legs"]), 2)
        == 4000.0
        for event in first["decisions"]
    )

    rows = _ledger_rows(first)
    assert len(rows) == 60
    assert len({row["record_id"] for row in rows}) == 60
    assert len({row["decision_id"] for row in rows}) == 10
    expected_url = fresh[0]["url"]
    expected_id = hashlib.sha256(expected_url.encode("utf-8")).hexdigest()
    assert exact_url_decision_id(expected_url) == expected_id
    expected_rows = [row for row in rows if row["decision_id"] == expected_id]
    assert len(expected_rows) == 6
    assert round(sum(row["paper_notional_usd"] for row in expected_rows), 2) == 4000.0
    assert all(row["first_seen_at"] == "2026-07-13T06:45:17Z" for row in rows)
    assert all(row["first_seen_at"] != row["published_at"] for row in rows)
    assert all(row["availability_timestamp_source"] == "first_seen_at" for row in rows)
    assert all(row["target_price"] is None for row in rows)
    assert all(row["target_price_status"] == TARGET_PRICE_STATUS for row in rows)
    assert all(row["exit_rule"] == "close_after_10_trading_sessions" for row in rows)
    assert all(row["hold_sessions"] == 10 for row in rows)
    assert all(row["outcome_status"] == "pending_10_trading_sessions" for row in rows)
    assert all(row["trade_enabled"] is False for row in rows)

    second = persist_entity_theme_news_event_forward_observer(
        "20260713",
        observed_at="2026-07-13T06:45:17Z",
        data_dir=tmp_path,
        ohlcv_by_ticker={},
    )
    assert second["decision_count"] == 0
    assert second["leg_count"] == 0
    assert second["rows_appended"] == 0
    assert second["decision_leg_count_total"] == 60
    assert len(_ledger_rows(second)) == 60


def test_outcome_waits_for_tenth_session_then_appends_cash_spy_qqq_once(tmp_path):
    _write_daily(
        tmp_path,
        "20260706",
        [
            _item(
                "https://news.example.test/ten-session-event",
                "2026-07-06T11:30:00Z",
                tickers=["TEST"],
            )
        ],
    )
    sessions = [
        "2026-07-06",
        "2026-07-07",
        "2026-07-08",
        "2026-07-09",
        "2026-07-10",
        "2026-07-13",
        "2026-07-14",
        "2026-07-15",
        "2026-07-16",
        "2026-07-17",
    ]
    ohlcv = {
        "TEST": _bars(sessions, 100.0, 110.0),
        "SPY": _bars(sessions, 100.0, 102.0),
        "QQQ": _bars(sessions, 100.0, 101.0),
    }

    immature = persist_entity_theme_news_event_forward_observer(
        "20260706",
        observed_at="2026-07-06T12:00:00Z",  # 08:00 ET, same-day open is next.
        data_dir=tmp_path,
        ohlcv_by_ticker=ohlcv,
    )
    assert immature["decision_count"] == 1
    assert immature["decision_rows_appended"] == 1
    assert immature["outcome_rows_appended"] == 0
    assert immature["settled_count"] == 0
    assert immature["pending_count"] == 1
    assert _ledger_rows(immature)[0]["row_type"] == "decision"

    mature = persist_entity_theme_news_event_forward_observer(
        "20260717",
        observed_at="2026-07-17T20:00:00Z",
        data_dir=tmp_path,
        ohlcv_by_ticker=ohlcv,
    )
    assert mature["decision_count"] == 0
    assert mature["decision_rows_appended"] == 0
    assert mature["outcome_rows_appended"] == 1
    assert mature["rows_appended"] == 1
    assert mature["settled_count"] == 1
    assert mature["settled_event_count"] == 1
    assert mature["pending_count"] == 0
    rows = _ledger_rows(mature)
    assert [row["row_type"] for row in rows] == ["decision", "outcome"]
    outcome = rows[1]
    assert outcome["entry_date"] == "2026-07-06"
    assert outcome["exit_date"] == "2026-07-17"
    assert outcome["pnl_usd"] == 400.0
    assert outcome["replacement_value_vs_cash_usd"] == 400.0
    assert outcome["replacement_value_vs_spy_usd"] == 320.0
    assert outcome["replacement_value_vs_qqq_usd"] == 360.0
    assert outcome["outcome_status"] == "settled"
    assert outcome["target_price"] is None
    assert outcome["trade_enabled"] is False

    rerun = persist_entity_theme_news_event_forward_observer(
        "20260717",
        observed_at="2026-07-17T20:00:00Z",
        data_dir=tmp_path,
        ohlcv_by_ticker=ohlcv,
    )
    assert rerun["rows_appended"] == 0
    assert rerun["settled_count"] == 1
    assert len(_ledger_rows(rerun)) == 2


def test_first_seen_after_open_not_published_at_selects_next_session(tmp_path):
    url = "https://news.example.test/policy-clock?version=one"
    assert exact_url_decision_id(url) != exact_url_decision_id(
        "https://news.example.test/policy-clock?version=two"
    )
    _write_daily(
        tmp_path,
        "20260706",
        [_item(url, "2026-07-06T12:00:00Z", tickers=["TEST"])],
    )
    sessions = [
        "2026-07-06",
        "2026-07-07",
        "2026-07-08",
        "2026-07-09",
        "2026-07-10",
        "2026-07-13",
        "2026-07-14",
        "2026-07-15",
        "2026-07-16",
        "2026-07-17",
        "2026-07-20",
    ]
    ohlcv = {
        "TEST": _bars(sessions, 100.0, 110.0),
        "SPY": _bars(sessions, 100.0, 102.0),
        "QQQ": _bars(sessions, 100.0, 101.0),
    }

    summary = persist_entity_theme_news_event_forward_observer(
        "20260720",
        # Published pre-open, but policy did not observe it until 10:00 ET.
        observed_at="2026-07-06T14:00:00Z",
        data_dir=tmp_path,
        ohlcv_by_ticker=ohlcv,
    )

    outcome = next(row for row in _ledger_rows(summary) if row["row_type"] == "outcome")
    assert outcome["published_at"] == "2026-07-06T12:00:00Z"
    assert outcome["first_seen_at"] == "2026-07-06T14:00:00Z"
    assert outcome["entry_date"] == "2026-07-07"
    assert outcome["exit_date"] == "2026-07-20"
