import json

import pandas as pd
import news_event_exposure_observer as observer

from news_event_exposure_observer import (
    SCHEMA_VERSION,
    build_exposure_rows,
    exposure_set_for_ticker,
    load_ledger,
    merge_rows,
    settle_rows,
    write_ledger,
)

EXPOSURE_MAP = {
    "sic_index": {
        "by_sic": {
            "7372": [
                {"ticker": "META", "cik": "1", "name": "M", "sic_description": ""},
                {"ticker": "CRWD", "cik": "2", "name": "C", "sic_description": ""},
                {"ticker": "SNOW", "cik": "3", "name": "S", "sic_description": ""},
            ]
        }
    },
    "overlay": {
        "overlay_version": "test_v1",
        "themes": [
            {
                "theme": "ai_software_platforms",
                "sic_codes": [],
                "name_keywords": [],
                "listed_peers": ["META", "PLTR", "NOW"],
            }
        ],
    },
    "ticker_sic": {"META": "7372", "CRWD": "7372", "SNOW": "7372"},
    "ticker_themes": {"META": ["ai_software_platforms"], "PLTR": ["ai_software_platforms"]},
}

EVENT = {
    "event_id": "ev-1",
    "event_date": "2026-06-30",
    "published_at": "2026-06-30T17:00:00+00:00",
    "ticker": "META",
    "relation_type": "customer_order_or_partnership",
    "relation_polarity": "negative",
    "rule_version": "daily_news_structured_event_ledger_v1",
}


def test_exposure_set_excludes_first_order_and_dedupes():
    edges = exposure_set_for_ticker("META", EXPOSURE_MAP)
    tickers = [e["exposure_ticker"] for e in edges]
    assert "META" not in tickers
    assert set(tickers) == {"CRWD", "SNOW", "PLTR", "NOW"}
    kinds = {e["exposure_ticker"]: e["relation_type"] for e in edges}
    assert kinds["CRWD"] == "sic_peer"
    assert kinds["PLTR"] == "theme_peer"


def test_sic_peer_cap():
    big_map = {
        "sic_index": {
            "by_sic": {
                "2836": [
                    {"ticker": f"T{i:03d}", "cik": str(i), "name": "", "sic_description": ""}
                    for i in range(40)
                ]
            }
        },
        "overlay": {"overlay_version": "v", "themes": []},
        "ticker_sic": {"T000": "2836"},
        "ticker_themes": {},
    }
    edges = exposure_set_for_ticker("T000", big_map)
    assert len(edges) == 14  # 15 cap minus the first-order ticker itself


def test_build_rows_carry_event_provenance():
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    assert len(rows) == 4
    row = rows[0]
    assert row["event_id"] == "ev-1"
    assert row["first_order_ticker"] == "META"
    assert row["event_polarity"] == "negative"
    assert row["outcome_status"] == "pending_forward_close"
    assert row["entry_date"] is None


def test_new_rows_share_immutable_local_first_seen_batch():
    first_seen_at = "2026-08-24T16:00:00+00:00"
    rows = build_exposure_rows(
        [EVENT], EXPOSURE_MAP, first_seen_at=first_seen_at
    )
    assert {row["schema_version"] for row in rows} == {SCHEMA_VERSION}
    assert {row["first_seen_at"] for row in rows} == {first_seen_at}
    assert len({row["first_seen_batch_id"] for row in rows}) == 1
    assert {
        row["entry_semantics"] for row in rows
    } == {"first_regular_session_open_after_first_seen_at"}

    legacy = build_exposure_rows([EVENT], EXPOSURE_MAP)
    assert all("first_seen_at" not in row for row in legacy)
    assert all("first_seen_batch_id" not in row for row in legacy)


def test_merge_preserves_original_first_seen_timestamp():
    original = build_exposure_rows(
        [EVENT], EXPOSURE_MAP, first_seen_at="2026-08-24T16:00:00+00:00"
    )
    duplicate = build_exposure_rows(
        [EVENT], EXPOSURE_MAP, first_seen_at="2026-08-24T17:00:00+00:00"
    )
    merged, appended = merge_rows(original, duplicate)
    assert appended == 0
    assert {row["first_seen_at"] for row in merged} == {
        "2026-08-24T16:00:00+00:00"
    }


def test_merge_rows_dedup():
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    merged, appended = merge_rows([], rows)
    assert appended == 4
    merged2, appended2 = merge_rows(merged, rows)
    assert appended2 == 0
    assert len(merged2) == 4


def _synthetic_frame(prices):
    idx = pd.bdate_range("2026-06-29", periods=len(prices))
    return pd.DataFrame(
        {
            "Open": prices,
            "High": prices,
            "Low": prices,
            "Close": prices,
            "Volume": [1e6] * len(prices),
        },
        index=idx,
    )


def test_settlement_math():
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    # exposure ticker rises 10% over 10 sessions, SPY flat -> excess ~ +10%
    frames = {
        t: _synthetic_frame([100.0 * (1.01**i) for i in range(15)])
        for t in ("CRWD", "SNOW", "PLTR", "NOW")
    }
    frames["SPY"] = _synthetic_frame([500.0] * 15)
    counts = settle_rows(rows, frames)
    assert counts["settled"] == 4
    row = rows[0]
    assert row["outcome_status"] == "closed"
    # event 06-30 -> entry next session 07-01 (index pos 2)
    assert row["entry_date"] == "2026-07-01"
    assert abs(row["excess_10d"] - ((1.01**9) - 1.0)) < 1e-5
    assert abs(row["excess_5d"] - ((1.01**4) - 1.0)) < 1e-5


def test_settlement_stays_pending_without_enough_bars():
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    frames = {
        t: _synthetic_frame([100.0] * 5) for t in ("CRWD", "SNOW", "PLTR", "NOW")
    }
    frames["SPY"] = _synthetic_frame([500.0] * 5)
    counts = settle_rows(rows, frames)
    assert counts["settled"] == 0
    assert counts["still_pending"] == 4


def test_v2_settlement_enters_after_first_seen_session_open_not_event_date():
    rows = build_exposure_rows(
        [EVENT],
        EXPOSURE_MAP,
        first_seen_at="2026-07-01T14:00:00-04:00",
    )
    frames = {
        ticker: _synthetic_frame([100.0] * 15)
        for ticker in ("CRWD", "SNOW", "PLTR", "NOW")
    }
    frames["SPY"] = _synthetic_frame([500.0] * 15)
    counts = settle_rows(rows, frames)
    assert counts["settled"] == 4
    # Event date was June 30, but local observation happened after the July 1
    # open, so July 1 is not executable and the first valid entry is July 2.
    assert {row["entry_date"] for row in rows} == {"2026-07-02"}


def test_write_and_reload_ledger(tmp_path):
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    manifest = write_ledger(rows, out_dir=tmp_path)
    assert manifest["rows"] == 4
    assert manifest["pending_rows"] == 4
    reloaded = load_ledger(tmp_path / "rows.jsonl")
    assert len(reloaded) == 4
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["rows"] == 4


def test_manifest_separates_first_seen_eligible_from_legacy_rows(tmp_path):
    legacy = build_exposure_rows([EVENT], EXPOSURE_MAP)
    current = build_exposure_rows(
        [{**EVENT, "event_id": "ev-2"}],
        EXPOSURE_MAP,
        first_seen_at="2026-08-24T16:00:00+00:00",
    )
    manifest = write_ledger(legacy + current, out_dir=tmp_path)
    assert manifest["first_seen_eligible_rows"] == 4
    assert manifest["legacy_ineligible_rows"] == 4


def test_run_persists_first_seen_rows_and_pair_readiness(monkeypatch, tmp_path):
    monkeypatch.setattr(observer, "load_exposure_map", lambda map_dir=None: EXPOSURE_MAP)
    monkeypatch.setattr(
        observer,
        "collect_structured_event_rows",
        lambda **kwargs: [EVENT],
    )
    monkeypatch.setattr(
        observer,
        "utc_now",
        lambda: "2026-08-24T16:00:00+00:00",
    )
    frames = {
        ticker: _synthetic_frame([100.0] * 15)
        for ticker in ("CRWD", "SNOW", "PLTR", "NOW")
    }
    frames["SPY"] = _synthetic_frame([500.0] * 15)

    manifest = observer.run(out_dir=tmp_path, frames=frames)

    assert manifest["first_seen_eligible_rows"] == 4
    assert manifest["legacy_ineligible_rows"] == 0
    assert manifest["pair_forward_readiness"]["batches"] == 1
    assert manifest["pair_forward_readiness"]["trade_enabled"] is False
    assert (tmp_path / "pair_forward_readiness" / "latest_snapshot.json").exists()
    rows = load_ledger(tmp_path / "rows.jsonl")
    assert {row["first_seen_at"] for row in rows} == {
        "2026-08-24T16:00:00+00:00"
    }
    assert manifest["short_side_borrow_prefetch"] == {
        "status": "skipped_non_production"
    }


POSITIVE_EVENT = {**EVENT, "event_id": "ev-pos", "relation_polarity": "positive"}


def test_prefetch_targets_only_new_positive_side_tickers(monkeypatch):
    import iborrowdesk_data_source

    monkeypatch.delenv("IBORROWDESK_REFRESH_DISABLED", raising=False)
    calls = {}

    def fake_refresh(tickers, **kwargs):
        calls["tickers"] = list(tickers)
        calls["kwargs"] = kwargs
        return {"succeeded": len(calls["tickers"])}

    monkeypatch.setattr(iborrowdesk_data_source, "refresh_archive", fake_refresh)
    existing = [
        row
        for row in build_exposure_rows([POSITIVE_EVENT], EXPOSURE_MAP)
        if row["exposure_ticker"] == "CRWD"
    ]
    summary = observer.prefetch_short_side_borrow(
        [EVENT, POSITIVE_EVENT], EXPOSURE_MAP, existing
    )
    assert summary["status"] == "ok"
    # Negative-polarity (long-side) rows and already-ledgered rows are excluded.
    assert summary["tickers"] == ["NOW", "PLTR", "SNOW"]
    assert calls["tickers"] == ["NOW", "PLTR", "SNOW"]
    assert calls["kwargs"]["max_fetches"] == 3


def test_prefetch_no_new_short_side_rows(monkeypatch):
    monkeypatch.delenv("IBORROWDESK_REFRESH_DISABLED", raising=False)
    summary = observer.prefetch_short_side_borrow([EVENT], EXPOSURE_MAP, [])
    assert summary == {"status": "no_new_short_side_rows", "tickers": []}


def test_prefetch_respects_env_opt_out(monkeypatch):
    monkeypatch.setenv("IBORROWDESK_REFRESH_DISABLED", "1")
    summary = observer.prefetch_short_side_borrow(
        [POSITIVE_EVENT], EXPOSURE_MAP, []
    )
    assert summary == {"status": "disabled"}


def test_prefetch_fails_open(monkeypatch):
    import iborrowdesk_data_source

    monkeypatch.delenv("IBORROWDESK_REFRESH_DISABLED", raising=False)

    def broken_refresh(tickers, **kwargs):
        raise RuntimeError("host down")

    monkeypatch.setattr(iborrowdesk_data_source, "refresh_archive", broken_refresh)
    summary = observer.prefetch_short_side_borrow(
        [POSITIVE_EVENT], EXPOSURE_MAP, []
    )
    assert summary["status"] == "failed"
    assert "host down" in summary["error"]
