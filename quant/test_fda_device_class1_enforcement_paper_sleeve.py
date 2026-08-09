from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import fda_device_class1_enforcement_paper_sleeve as sleeve


def _raw_row(
    *,
    firm: str = "Boston Scientific Corporation",
    event_id: str = "Z-1000-2025",
    report_date: str = "20250103",
    recall_number: str = "Z-1000-2025",
    classification: str = "Class I",
    source_hash: str = "a" * 64,
):
    return {
        "raw_record": {
            "event_id": event_id,
            "recalling_firm": firm,
            "classification": classification,
            "report_date": report_date,
            "recall_number": recall_number,
            "product_description": f"Device {recall_number}",
            "status": "Ongoing",
            "recall_initiation_date": "20241220",
            "center_classification_date": "20250102",
            "initial_firm_notification": "Letter",
        },
        "source_url": "https://api.fda.gov/device/enforcement.json?search=frozen",
        "raw_sha256": source_hash,
    }


def _event(**kwargs):
    return sleeve.normalise_fda_device_class1_enforcement_events([_raw_row(**kwargs)])[0]


def _bars(closes, start_day=1):
    return [
        {
            "Date": f"2025-01-{idx + start_day:02d}",
            "Open": close - 0.2,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
        }
        for idx, close in enumerate(closes)
    ]


def test_exact_preregistered_firm_map_and_holx_exclusion():
    assert len(sleeve.FIRM_TO_TICKER) == 36
    assert len(set(sleeve.FIRM_TO_TICKER.values())) == 19
    assert sleeve.FIRM_TO_TICKER["Boston Scientific Corporation"] == "BSX"
    assert sleeve.FIRM_TO_TICKER["PHILIPS MEDICAL SYSTEMS NEDERLAND B.V."] == "PHG"
    assert sleeve.FIRM_TO_TICKER["DATEX--OHMEDA, INC."] == "GEHC"
    assert "HOLX" not in sleeve.FIRM_TO_TICKER.values()


def test_class1_exact_firm_filter_and_event_level_dedupe():
    rows = sleeve.normalise_fda_device_class1_enforcement_events(
        [
            _raw_row(recall_number="Z-1000-2025", source_hash="a" * 64),
            _raw_row(recall_number="Z-1001-2025", source_hash="b" * 64),
            _raw_row(
                firm="Unregistered Device Firm",
                event_id="Z-2000-2025",
                source_hash="c" * 64,
            ),
            _raw_row(
                event_id="Z-3000-2025",
                classification="Class II",
                source_hash="d" * 64,
            ),
        ]
    )
    assert len(rows) == 1
    assert rows[0]["ticker"] == "BSX"
    assert rows[0]["classification"] == "Class I"
    assert rows[0]["report_date"] == "2025-01-03"
    assert rows[0]["recall_numbers"] == ["Z-1000-2025", "Z-1001-2025"]
    assert rows[0]["source_record_count"] == 2


def test_historical_event_without_official_provenance_fails_closed():
    row = _raw_row()
    row.pop("source_url")
    assert sleeve.normalise_fda_device_class1_enforcement_events([row]) == []


def test_fetch_freezes_canonical_api_page_and_manifest(monkeypatch, tmp_path):
    raw_a = _raw_row(recall_number="Z-1000-2025")["raw_record"]
    raw_b = _raw_row(recall_number="Z-1001-2025")["raw_record"]
    payload = {"meta": {"results": {"total": 2}}, "results": [raw_a, raw_b]}
    requested = []

    def fake_get(url, *, timeout):
        requested.append((url, timeout))
        return payload

    monkeypatch.setattr(sleeve, "_get_json", fake_get)
    rows = sleeve.fetch_fda_device_class1_enforcement_events(
        "2025-01-01",
        "2025-01-31",
        timeout=9.0,
        archive_payload_dir=tmp_path,
    )
    assert len(rows) == 1
    assert rows[0]["source_record_count"] == 2
    assert "classification%3A%22Class+I%22" in requested[0][0]
    page_path = tmp_path / "openfda_device_enforcement_page_000000.json"
    manifest = json.loads((tmp_path / "openfda_fetch_manifest.json").read_text())
    assert manifest["raw_record_count"] == 2
    assert manifest["retrieved_at"].endswith("+00:00")
    assert manifest["pages"][0]["sha256"] == hashlib.sha256(page_path.read_bytes()).hexdigest()


def test_archive_round_trip_verifies_event_hash(tmp_path):
    path = tmp_path / "events.json"
    saved = sleeve.save_fda_device_class1_enforcement_archive(path, [_event()])
    loaded = sleeve.load_fda_device_class1_enforcement_archive(path)
    assert saved["event_count"] == 1
    assert saved["ticker_count"] == 1
    assert loaded[0]["event_id"] == "Z-1000-2025"
    assert loaded[0]["raw_sha256"] == saved["events"][0]["raw_sha256"]


def test_refresh_archive_load_verifies_raw_manifest_pages_and_records(monkeypatch, tmp_path):
    payload = {
        "meta": {"results": {"total": 1}},
        "results": [_raw_row()["raw_record"]],
    }
    monkeypatch.setattr(sleeve, "_get_json", lambda url, *, timeout: payload)
    archive_path = tmp_path / "events.json"
    raw_dir = tmp_path / "raw"
    saved = sleeve.refresh_fda_device_class1_enforcement_archive(
        archive_path,
        start="2025-01-01",
        end="2025-01-31",
        archive_payload_dir=raw_dir,
    )
    assert saved["raw_payload_manifest_sha256"]
    assert len(sleeve.load_fda_device_class1_enforcement_archive(archive_path)) == 1
    (raw_dir / "openfda_device_enforcement_page_000000.json").write_text("{}")
    with pytest.raises(RuntimeError, match="raw page hash mismatch"):
        sleeve.load_fda_device_class1_enforcement_archive(archive_path)


def test_strict_after_confirmation_top1_and_replay_cost_contract():
    events = [
        _event(),
        _event(
            firm="Baxter Healthcare Corporation",
            event_id="Z-2000-2025",
            recall_number="Z-2000-2025",
            source_hash="b" * 64,
        ),
    ]
    # Jan 3 is report_date and is never eligible. Jan 4 confirmation returns:
    # BSX +2%, BAX +1%, SPY flat, therefore BSX wins top-1.
    ohlcv = {
        "SPY": _bars([100] * 20),
        "BSX": _bars([100, 100, 100, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118]),
        "BAX": _bars([100, 100, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117]),
    }
    replay = sleeve.replay_fda_device_class1_enforcement_paper_trades(
        events=events,
        ohlcv_by_ticker=ohlcv,
        start="2025-01-01",
        end="2025-01-20",
    )
    assert replay["signals_generated"] == 2
    assert replay["signals_survived"] == 1
    assert replay["reject_totals"]["daily_top1_limit"] == 1
    trade = replay["trades"][0]
    assert trade["ticker"] == "BSX"
    assert trade["signal_date"] == "2025-01-04"
    assert trade["entry_date"] == "2025-01-05"
    # Entry day is session 1, so Jan 14 is the tenth session's close.
    assert trade["exit_date"] == "2025-01-14"
    assert trade["scheduled_exit_date"] == "2025-01-14"
    assert trade["hold_days"] == 10
    assert trade["hold_sessions_realized"] == 10
    expected = 4_000 * (112 / 102.8 - 1 - 0.0035)
    assert trade["pnl"] == pytest.approx(expected, abs=0.01)
    assert trade["target_price"] > trade["entry_price"]
    assert trade["trade_enabled"] is False


def test_same_ticker_ten_session_cooldown():
    events = [
        _event(event_id="Z-1000-2025", report_date="20250103"),
        _event(
            event_id="Z-1001-2025",
            report_date="20250108",
            recall_number="Z-1001-2025",
            source_hash="b" * 64,
        ),
    ]
    spy = _bars([100] * 20)
    bsx = _bars([100, 100, 100, 102, 102, 102, 102, 102, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115])
    selected, rejects = sleeve.build_fda_device_class1_enforcement_candidates(
        events=events,
        ohlcv_by_ticker={"SPY": spy, "BSX": bsx},
        start="2025-01-01",
        end="2025-01-20",
    )
    assert len(selected) == 1
    assert rejects["same_ticker_cooldown"] == 1


def test_daily_old_discovery_is_seed_only_and_default_off():
    snapshot, observations = (
        sleeve.prep_and_build_fda_device_class1_enforcement_paper_sleeve_snapshot(
            as_of_date="20260713",
            existing_observations=[],
            fetched_events=[_event(report_date="20260701")],
        )
    )
    assert observations[0]["first_seen_date"] == "2026-07-13"
    assert snapshot["candidate_count"] == 0
    assert snapshot["pending_confirmation_count"] == 0
    assert snapshot["seed_only_count"] == 1
    assert snapshot["late_first_seen_count"] == 1
    assert snapshot["seed_reason_counts"] == {
        "late_first_seen_after_report_date": 1
    }
    assert snapshot["seed_only_observations"][0]["snapshot_seed_reason"] == (
        "late_first_seen_after_report_date"
    )
    assert observations[0]["forward_eligibility"] == "seed_only"
    assert observations[0]["seed_only_reason"] == "late_first_seen_after_report_date"
    assert snapshot["trade_enabled"] is False
    assert snapshot["alters_signal_generation"] is False
    assert snapshot["alters_candidate_ranking"] is False


def test_today_first_seen_is_pending_confirmation_not_candidate():
    snapshot, _ = (
        sleeve.prep_and_build_fda_device_class1_enforcement_paper_sleeve_snapshot(
            as_of_date="2026-07-13",
            existing_observations=[],
            fetched_events=[_event(report_date="20260713")],
        )
    )
    assert snapshot["candidate_count"] == 0
    assert snapshot["pending_confirmation_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["settled_count"] == 0
    assert snapshot["late_first_seen_count"] == 0
    assert snapshot["seed_reason_counts"] == {}
    assert snapshot["trade_enabled"] is False


def test_as_of_and_empty_state_contracts():
    snapshot = sleeve.build_fda_device_class1_enforcement_paper_sleeve_snapshot(
        as_of_date="20260713", observations=[]
    )
    assert snapshot["as_of_date"] == "2026-07-13"
    assert sleeve.empty_fda_device_class1_enforcement_paper_state() == {
        "observations": [],
        "pending": [],
        "open": [],
        "closed": [],
    }
