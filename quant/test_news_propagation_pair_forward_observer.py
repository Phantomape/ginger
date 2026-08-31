from __future__ import annotations

import copy
import json

from news_propagation_pair_forward_observer import (
    EXPOSURE_SCHEMA_VERSION,
    build_readiness_records,
    build_snapshot,
    run,
)


FIRST_SEEN = "2026-08-24T16:00:00+00:00"
BATCH_ID = "news-first-seen-test"


def _exposure_rows():
    rows = []
    for polarity, prefix in (("negative", "L"), ("positive", "S")):
        for index in range(3):
            rows.append(
                {
                    "schema_version": EXPOSURE_SCHEMA_VERSION,
                    "event_id": f"{polarity}-{index}",
                    "exposure_ticker": f"{prefix}{index}",
                    "event_polarity": polarity,
                    "first_seen_at": FIRST_SEEN,
                    "first_seen_batch_id": BATCH_ID,
                    "excess_5d": 99.0,
                    "excess_10d": 99.0,
                    "outcome_status": "closed",
                }
            )
    return rows


def _borrow_histories(*, row_date="2026-08-24", archived_at="2026-08-24T15:00:00+00:00"):
    return {
        f"S{index}": {
            "rows": {
                row_date: {
                    "archived_at": archived_at,
                    "available": 100_000,
                    "fee": 0.5,
                }
            }
        }
        for index in range(3)
    }


def test_ready_batch_is_diversified_borrow_covered_and_non_executable():
    records = build_readiness_records(_exposure_rows(), _borrow_histories())
    assert len(records) == 1
    record = records[0]
    assert record["status"] == "measurement_ready"
    assert record["blockers"] == []
    assert record["borrow_coverage"]["covered_tickers"] == 3
    assert record["borrow_coverage"]["is_broker_locate"] is False
    assert record["pnl_measured"] is False
    assert record["strategy_behavior_changed"] is False
    assert record["trade_enabled"] is False
    assert record["signals"] == []
    assert record["order_intents"] == []
    assert record["orders"] == []


def test_outcome_fields_cannot_change_readiness_decision():
    rows = _exposure_rows()
    before = build_readiness_records(rows, _borrow_histories())
    mutated = copy.deepcopy(rows)
    for row in mutated:
        row["excess_5d"] = -12345.0
        row["excess_10d"] = None
        row["outcome_status"] = "pending_forward_close"
    assert build_readiness_records(mutated, _borrow_histories()) == before


def test_missing_or_stale_borrow_fails_closed():
    stale = build_readiness_records(
        _exposure_rows(), _borrow_histories(row_date="2026-08-20")
    )[0]
    assert stale["status"] == "blocked"
    assert any(value.startswith("stale_pit_borrow:") for value in stale["blockers"])

    histories = _borrow_histories()
    del histories["S1"]
    missing = build_readiness_records(_exposure_rows(), histories)[0]
    assert missing["status"] == "blocked"
    assert "missing_pit_borrow:S1" in missing["blockers"]

    future_archive = build_readiness_records(
        _exposure_rows(),
        _borrow_histories(archived_at="2026-08-24T17:00:00+00:00"),
    )[0]
    assert future_archive["status"] == "blocked"
    assert any(
        value.startswith("missing_pit_borrow:")
        for value in future_archive["blockers"]
    )


def test_legacy_rows_are_never_admitted_or_backfilled():
    rows = _exposure_rows()
    rows.extend(
        [
            {
                "schema_version": "news_event_exposure_observation_v1",
                "event_id": "legacy",
                "exposure_ticker": "OLD",
                "event_polarity": "positive",
            },
            {
                "schema_version": EXPOSURE_SCHEMA_VERSION,
                "event_id": "naive-clock",
                "exposure_ticker": "BAD",
                "event_polarity": "positive",
                "first_seen_at": "2026-08-24T16:00:00",
                "first_seen_batch_id": "invalid-batch",
            },
        ]
    )
    snapshot = build_snapshot(rows, _borrow_histories())
    assert snapshot["first_seen_eligible_rows"] == 6
    assert snapshot["legacy_or_ineligible_rows"] == 2
    assert "OLD" not in snapshot["records"][0]["short_side"]["tickers"]
    assert "BAD" not in snapshot["records"][0]["short_side"]["tickers"]


def test_cross_side_overlap_blocks_batch():
    rows = _exposure_rows()
    rows[3]["exposure_ticker"] = "L0"
    histories = _borrow_histories()
    histories["L0"] = histories.pop("S0")
    record = build_readiness_records(rows, histories)[0]
    assert record["status"] == "blocked"
    assert record["cross_side_ticker_overlap"] == ["L0"]
    assert "cross_side_ticker_overlap" in record["blockers"]


def test_persistence_is_idempotent(tmp_path):
    first = run(
        exposure_rows=_exposure_rows(),
        borrow_histories=_borrow_histories(),
        out_dir=tmp_path,
    )
    first_snapshot = (tmp_path / "latest_snapshot.json").read_text(encoding="utf-8")
    second = run(
        exposure_rows=_exposure_rows(),
        borrow_histories=_borrow_histories(),
        out_dir=tmp_path,
    )
    assert first["appended_this_run"] == 1
    assert second["appended_this_run"] == 0
    lines = (tmp_path / "readiness_decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["record_id"] == first["records"][0]["record_id"]
    assert (tmp_path / "latest_snapshot.json").read_text(encoding="utf-8") == first_snapshot
