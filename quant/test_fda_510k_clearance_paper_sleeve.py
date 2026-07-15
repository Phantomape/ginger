from __future__ import annotations

import json
import gzip
import hashlib
from datetime import date, timedelta

import pytest

from quant.fda_510k_clearance_paper_sleeve import (
    APPLICANT_TO_TICKER,
    BASE_NOTIONAL_USD,
    ROUND_TRIP_COST_PCT,
    build_fda_510k_clearance_paper_snapshot,
    load_fda_510k_clearance_archive,
    normalise_fda_510k_clearance_events,
    replay_fda_510k_clearance_paper_trades,
    save_fda_510k_clearance_archive,
    verify_fda_510k_raw_manifest,
)


def _business_bars(start: str, count: int, *, slope: float = 1.0):
    day = date.fromisoformat(start)
    rows = []
    index = 0
    while len(rows) < count:
        if day.weekday() < 5:
            close = 100.0 + index * slope
            rows.append(
                {
                    "date": day.isoformat(),
                    "open": close - 0.25,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                }
            )
            index += 1
        day += timedelta(days=1)
    return rows


def _row(k_number="K250001", decision_date="2025-01-02", **overrides):
    row = {
        "k_number": k_number,
        "applicant": "Intuitive Surgical, Inc.",
        "clearance_type": "Traditional",
        "decision_date": decision_date,
        "device_name": "Example system",
        "product_code": "XYZ",
        "decision_description": "Substantially Equivalent",
    }
    row.update(overrides)
    return row


def test_applicant_mapping_is_exact_and_excludes_known_substring_collisions():
    assert APPLICANT_TO_TICKER["INTUITIVE SURGICAL INC"] == "ISRG"
    rows = normalise_fda_510k_clearance_events(
        [
            _row(applicant="Vitalconnect, Inc."),
            _row(k_number="K250002", applicant="Change Healthcare Canada Company"),
            _row(k_number="K250003", applicant="Merge Healthcare Incorporated"),
            _row(k_number="K250004", applicant="Fresenius Kabi AG"),
            _row(k_number="K250005", applicant="3M Company"),
        ]
    )
    assert rows == []


def test_normalisation_uses_traditional_only_and_fourteen_day_envelope():
    rows = normalise_fda_510k_clearance_events(
        [
            _row(),
            _row(k_number="K250002", clearance_type="Special"),
            _row(k_number="K250003", applicant="Unmapped Private Device Co."),
        ]
    )
    assert len(rows) == 1
    event = rows[0]
    assert event["ticker"] == "ISRG"
    assert event["decision_date"] == "2025-01-02"
    assert event["public_as_of"] == "2025-01-16"
    assert event["trade_enabled"] is False
    assert len(event["source_record_sha256"]) == 64


def test_replay_enters_strictly_after_envelope_and_holds_ten_sessions():
    bars = _business_bars("2025-01-01", 45, slope=0.7)
    events = normalise_fda_510k_clearance_events([_row()])
    replay = replay_fda_510k_clearance_paper_trades(
        events=events,
        ohlcv_by_ticker={"ISRG": bars},
        start="2025-01-01",
        end="2025-03-31",
    )
    assert replay["trade_enabled"] is False
    assert len(replay["trades"]) == 1
    trade = replay["trades"][0]
    assert trade["signal_date"] == "2025-01-16"
    assert trade["entry_date"] > trade["signal_date"]
    assert trade["hold_sessions_realized"] == 10
    entry_index = next(i for i, row in enumerate(bars) if row["date"] == trade["entry_date"])
    assert trade["exit_date"] == bars[entry_index + 9]["date"]
    expected = BASE_NOTIONAL_USD * (
        trade["exit_price"] / trade["entry_price"] - 1.0 - ROUND_TRIP_COST_PCT
    )
    assert trade["pnl"] == pytest.approx(expected, abs=0.02)
    assert trade["target_price"] > trade["entry_price"]


def test_one_issuer_day_and_ticker_cooldown_are_deterministic():
    bars = _business_bars("2025-01-01", 70, slope=0.2)
    events = normalise_fda_510k_clearance_events(
        [
            _row(k_number="K250002"),
            _row(k_number="K250001"),
            _row(k_number="K250003", decision_date="2025-01-09"),
        ]
    )
    replay = replay_fda_510k_clearance_paper_trades(
        events=events,
        ohlcv_by_ticker={"ISRG": bars},
        start="2025-01-01",
        end="2025-04-30",
    )
    assert [row["k_number"] for row in replay["trades"]] == ["K250001"]
    assert replay["reject_totals"]["same_ticker_cooldown"] == 1


def test_archive_roundtrip_and_tamper_detection(tmp_path):
    path = tmp_path / "events.json"
    events = normalise_fda_510k_clearance_events([_row()])
    saved = save_fda_510k_clearance_archive(path, events)
    assert saved["event_count"] == 1
    assert load_fda_510k_clearance_archive(path) == events

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["events"][0]["device_name"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_fda_510k_clearance_archive(path)


def test_raw_manifest_verifies_compressed_and_uncompressed_hashes(tmp_path):
    raw = json.dumps({"results": [{"k_number": "K250001"}]}).encode("utf-8")
    archived = gzip.compress(raw, mtime=0)
    page = tmp_path / "page.json.gz"
    page.write_bytes(archived)
    manifest = {
        "schema": "fda_510k_raw_api_manifest_v1",
        "raw_record_count": 1,
        "pages": [
            {
                "path": page.name,
                "record_count": 1,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "archive_sha256": hashlib.sha256(archived).hexdigest(),
                "compression": "gzip",
            }
        ],
    }
    (tmp_path / "openfda_fetch_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    verified = verify_fda_510k_raw_manifest(tmp_path)
    assert verified["page_count"] == 1
    assert verified["raw_record_count"] == 1

    page.write_bytes(archived + b"tamper")
    with pytest.raises(ValueError, match="compressed page hash mismatch"):
        verify_fda_510k_raw_manifest(tmp_path)


def test_daily_snapshot_is_default_off():
    events = normalise_fda_510k_clearance_events([_row()])
    snapshot = build_fda_510k_clearance_paper_snapshot(
        events=events,
        ohlcv_by_ticker={"ISRG": _business_bars("2025-01-01", 45)},
        as_of="2025-03-20",
    )
    assert snapshot["trade_enabled"] is False
    assert snapshot["alters_orders"] is False
    assert snapshot["alters_candidate_ranking"] is False
    assert snapshot["alters_sizing"] is False
    assert snapshot["alters_exits"] is False
    assert snapshot["closed_trade_count"] == 1
