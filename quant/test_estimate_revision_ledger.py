from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from earnings_snapshot import persist_earnings_snapshot
from estimate_revision_ledger import (
    annotate_rows_with_signal_matches,
    build_revision_ledger_rows,
    load_daily_signal_match_records,
    load_snapshot_records,
    persist_estimate_revision_ledger,
    summarize_ledger_rows,
)


def _write_snapshot(
    root: Path,
    tag: str,
    earnings: dict,
    *,
    mtime: datetime,
    schema_version: int = 3,
    timestamp: str | None = None,
) -> None:
    normalized = {}
    for ticker, raw in earnings.items():
        row = dict(raw)
        if schema_version >= 3 and row.get("eps_estimate") is not None:
            row.setdefault(
                "eps_estimate_source",
                "yfinance.get_earnings_dates.EPS Estimate",
            )
            row.setdefault("eps_estimate_event_date", row.get("next_earnings_date"))
            row.setdefault(
                "observed_at",
                timestamp if timestamp is not None else mtime.isoformat(),
            )
        normalized[ticker] = row
    path = root / f"earnings_snapshot_{tag}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "date": tag,
                "timestamp": timestamp if timestamp is not None else mtime.isoformat(),
                "earnings": normalized,
            }
        ),
        encoding="utf-8",
    )
    ts = mtime.timestamp()
    os.utime(path, (ts, ts))


def test_persist_earnings_snapshot_keeps_next_earnings_date(tmp_path):
    path = persist_earnings_snapshot(
        {
            "ACME": {
                "next_earnings_date": "2026-07-30",
                "days_to_earnings": 30,
                "eps_estimate": 1.23,
                "ignored": "not persisted",
            }
        },
        as_of=datetime(2026, 5, 7),
        base_dir=tmp_path,
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["earnings"]["ACME"]["next_earnings_date"] == "2026-07-30"
    assert payload["earnings"]["ACME"]["next_earnings_date_inferred"] is False
    assert "ignored" not in payload["earnings"]["ACME"]


def test_persist_earnings_snapshot_infers_next_date_from_dte(tmp_path):
    path = persist_earnings_snapshot(
        {
            "ACME": {
                "days_to_earnings": 3,
                "eps_estimate": 1.23,
            }
        },
        as_of=datetime(2026, 5, 7),
        base_dir=tmp_path,
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    row = payload["earnings"]["ACME"]
    assert row["next_earnings_date"] == "2026-05-12"
    assert row["next_earnings_date_source"] == "derived_from_days_to_earnings"
    assert row["next_earnings_date_inferred"] is True
    assert payload["coverage"]["tickers_with_next_earnings_date"] == 1
    assert payload["coverage"]["tickers_with_inferred_next_earnings_date"] == 1


def test_persist_earnings_snapshot_rewrites_existing_when_next_date_improves(tmp_path):
    legacy_path = tmp_path / "earnings_snapshot_20260507.json"
    legacy_path.write_text(
        json.dumps(
            {
                "date": "20260507",
                "timestamp": "2026-05-07T00:00:00",
                "coverage": {
                    "tickers_total": 1,
                    "tickers_persisted": 1,
                    "tickers_with_days_to_earnings": 1,
                    "tickers_with_eps_estimate": 1,
                },
                "earnings": {
                    "ACME": {
                        "days_to_earnings": 3,
                        "eps_estimate": 1.23,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    path = persist_earnings_snapshot(
        {
            "ACME": {
                "days_to_earnings": 3,
                "eps_estimate": 1.23,
            }
        },
        as_of=datetime(2026, 5, 7),
        base_dir=tmp_path,
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert payload["earnings"]["ACME"]["next_earnings_date"] == "2026-05-12"
    assert payload["coverage"]["tickers_with_next_earnings_date"] == 1


def test_revision_ledger_marks_same_event_forward_delta_pit_safe(tmp_path):
    _write_snapshot(
        tmp_path,
        "20260506",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.00}},
        mtime=datetime(2026, 5, 6, 22, 0, tzinfo=timezone.utc),
    )
    _write_snapshot(
        tmp_path,
        "20260507",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.10}},
        mtime=datetime(2026, 5, 7, 22, 0, tzinfo=timezone.utc),
    )

    rows = build_revision_ledger_rows(
        load_snapshot_records(tmp_path),
        as_of="2026-05-07",
        generated_at=datetime(2026, 5, 7, 23, 0, tzinfo=timezone.utc),
    )

    assert len(rows) == 1
    assert rows[0]["eps_estimate_delta_prev"] == 0.1
    assert rows[0]["revision_direction_prev"] == "up"
    assert rows[0]["estimate_revision_usable"] is True
    assert rows[0]["pit_safe_flag"] is True
    assert summarize_ledger_rows(rows)["up_revision_rows"] == 1


def test_revision_ledger_rejects_changed_event_identity(tmp_path):
    _write_snapshot(
        tmp_path,
        "20260506",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.00}},
        mtime=datetime(2026, 5, 6, 22, 0, tzinfo=timezone.utc),
    )
    _write_snapshot(
        tmp_path,
        "20260507",
        {"ACME": {"next_earnings_date": "2026-10-30", "eps_estimate": 1.10}},
        mtime=datetime(2026, 5, 7, 22, 0, tzinfo=timezone.utc),
    )

    rows = build_revision_ledger_rows(load_snapshot_records(tmp_path), as_of="2026-05-07")

    assert rows[0]["prior_snapshot_eps_estimate"] is None
    assert rows[0]["estimate_revision_usable"] is False
    assert rows[0]["pit_caveat"] == "no_prior_same_event_snapshot"


def test_revision_ledger_flags_backfilled_snapshots_not_pit(tmp_path):
    _write_snapshot(
        tmp_path,
        "20260506",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.00}},
        mtime=datetime(2026, 5, 9, 22, 0, tzinfo=timezone.utc),
    )
    _write_snapshot(
        tmp_path,
        "20260507",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.10}},
        mtime=datetime(2026, 5, 9, 22, 0, tzinfo=timezone.utc),
    )

    rows = build_revision_ledger_rows(load_snapshot_records(tmp_path), as_of="2026-05-07")

    assert rows[0]["eps_estimate_delta_prev"] == 0.1
    assert rows[0]["estimate_revision_usable"] is False
    assert rows[0]["pit_caveat"] == "current_snapshot_created_after_asof"


def test_revision_ledger_prefers_pit_safe_organized_snapshot_duplicate(tmp_path):
    data_dir = tmp_path / "data"
    organized_dir = data_dir / "daily" / "snapshots" / "earnings"
    data_dir.mkdir()
    organized_dir.mkdir(parents=True)
    _write_snapshot(
        organized_dir,
        "20260519",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.00}},
        mtime=datetime(2026, 5, 20, 4, 0, tzinfo=timezone.utc),
    )
    _write_snapshot(
        data_dir,
        "20260519",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 9.00}},
        mtime=datetime(2026, 5, 24, 4, 0, tzinfo=timezone.utc),
    )
    _write_snapshot(
        organized_dir,
        "20260520",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.20}},
        mtime=datetime(2026, 5, 21, 4, 0, tzinfo=timezone.utc),
    )

    records = load_snapshot_records(data_dir)
    prior = [record for record in records if record["as_of_date"].isoformat() == "2026-05-19"]
    rows = build_revision_ledger_rows(records, as_of="2026-05-20")

    assert len(prior) == 1
    assert prior[0]["path"] == organized_dir / "earnings_snapshot_20260519.json"
    assert rows[0]["prior_snapshot_eps_estimate"] == 1.0
    assert rows[0]["prior_snapshot_pit_safe"] is True
    assert rows[0]["eps_estimate_delta_prev"] == 0.2
    assert rows[0]["estimate_revision_usable"] is True


def test_persist_estimate_revision_ledger_writes_default_off_artifacts(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "non_ohlcv"
    data_dir.mkdir()
    _write_snapshot(
        data_dir,
        "20260506",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.00}},
        mtime=datetime(2026, 5, 6, 22, 0, tzinfo=timezone.utc),
    )
    _write_snapshot(
        data_dir,
        "20260507",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.10}},
        mtime=datetime(2026, 5, 7, 22, 0, tzinfo=timezone.utc),
    )

    summary = persist_estimate_revision_ledger(
        as_of="2026-05-07",
        data_dir=data_dir,
        output_dir=output_dir,
        generated_at=datetime(2026, 5, 7, 23, 0, tzinfo=timezone.utc),
    )

    assert summary["row_count"] == 1
    assert summary["estimate_revision_usable_rows"] == 1
    assert summary["production_impact"]["alters_signal_generation"] is False
    assert summary["production_impact"]["alters_candidate_ranking"] is False
    assert summary["production_impact"]["alters_sizing"] is False
    assert summary["production_impact"]["alters_orders"] is False
    assert (output_dir / "estimate_revision_ledger_20260507.jsonl").exists()
    assert (output_dir / "estimate_revision_ledger_summary_20260507.json").exists()


def test_revision_ledger_marks_daily_candidate_and_signal_matches(tmp_path):
    _write_snapshot(
        tmp_path,
        "20260506",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.00}},
        mtime=datetime(2026, 5, 6, 22, 0, tzinfo=timezone.utc),
    )
    _write_snapshot(
        tmp_path,
        "20260507",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.10}},
        mtime=datetime(2026, 5, 7, 22, 0, tzinfo=timezone.utc),
    )
    (tmp_path / "quant_signals_20260507.json").write_text(
        json.dumps(
            {
                "signals": [
                    {
                        "ticker": "ACME",
                        "strategy": "breakout_long",
                        "action": "buy",
                        "trade_enabled": True,
                    }
                ],
                "entry_execution_plan": {"slot_sliced_signals": []},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "trend_signals_20260507.json").write_text(
        json.dumps(
            {
                "signals": {
                    "ACME": {
                        "breakout": True,
                        "above_200ma": True,
                        "volume_spike": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    rows = build_revision_ledger_rows(load_snapshot_records(tmp_path), as_of="2026-05-07")
    match_records = load_daily_signal_match_records(tmp_path, "2026-05-07")
    annotate_rows_with_signal_matches(rows, match_records)
    summary = summarize_ledger_rows(rows)

    assert rows[0]["matched_feature_row_today"] is True
    assert rows[0]["matched_candidate_today"] is True
    assert rows[0]["matched_selected_signal_today"] is True
    assert rows[0]["matched_candidate_count"] == 1
    assert rows[0]["matched_selected_signal_count"] == 1
    assert "breakout_long" in rows[0]["matched_signal_strategies"]
    assert "breakout_feature" in rows[0]["matched_signal_strategies"]
    assert rows[0]["candidate_match_gap_reason"] is None
    assert summary["matched_candidate_rows"] == 1
    assert summary["matched_selected_signal_rows"] == 1
    assert summary["estimate_revision_usable_and_matched_candidate_rows"] == 1


def test_revision_ledger_keeps_feature_rows_separate_from_candidates(tmp_path):
    _write_snapshot(
        tmp_path,
        "20260507",
        {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.10}},
        mtime=datetime(2026, 5, 7, 22, 0, tzinfo=timezone.utc),
    )
    (tmp_path / "trend_signals_20260507.json").write_text(
        json.dumps({"signals": {"ACME": {"breakout": True, "above_200ma": True}}}),
        encoding="utf-8",
    )

    rows = build_revision_ledger_rows(load_snapshot_records(tmp_path), as_of="2026-05-07")
    match_records = load_daily_signal_match_records(tmp_path, "2026-05-07")
    annotate_rows_with_signal_matches(rows, match_records)
    summary = summarize_ledger_rows(rows)

    assert rows[0]["matched_feature_row_today"] is True
    assert rows[0]["matched_candidate_today"] is False
    assert rows[0]["matched_selected_signal_today"] is False
    assert rows[0]["candidate_match_gap_reason"] == "feature_row_only_no_persisted_candidate_object"
    assert summary["matched_feature_rows"] == 1
    assert summary["matched_candidate_rows"] == 0


def test_write_jsonl_survives_concurrent_memory_map_of_destination(tmp_path):
    # Regression for exp-20260708-007: a truncating open("w") on the final
    # path raises OSError Errno 22 (ERROR_USER_MAPPED_FILE) on Windows while
    # another process holds the file memory-mapped, dropping the daily ledger.
    # The atomic temp+replace writer must ride out a short-lived mapping.
    import mmap
    import threading
    import time

    from estimate_revision_ledger import write_json, write_jsonl

    target = tmp_path / "estimate_revision_ledger_20260707.jsonl"
    write_jsonl(target, [{"ticker": "OLD"}])

    handle = open(target, "rb")
    mapping = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)

    def _release_after_delay():
        time.sleep(0.25)
        mapping.close()
        handle.close()

    releaser = threading.Thread(target=_release_after_delay)
    releaser.start()
    try:
        write_jsonl(target, [{"ticker": "NEW"}, {"ticker": "NEW2"}])
    finally:
        releaser.join()

    lines = target.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["ticker"] for line in lines] == ["NEW", "NEW2"]
    leftovers = list(tmp_path.glob(".*.tmp"))
    assert leftovers == []

    write_json(tmp_path / "summary.json", {"row_count": 2})
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == {
        "row_count": 2
    }


def test_revision_ledger_fails_closed_on_naive_decision_clock(tmp_path):
    for tag, estimate in (("20260506", 1.0), ("20260507", 1.1)):
        _write_snapshot(
            tmp_path,
            tag,
            {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": estimate}},
            mtime=datetime(2026, 5, int(tag[-2:]), 22, 0, tzinfo=timezone.utc),
            timestamp=f"2026-05-{tag[-2:]}T18:00:00",
        )

    row = build_revision_ledger_rows(
        load_snapshot_records(tmp_path), as_of="2026-05-07"
    )[0]

    assert row["decision_clock"] is None
    assert row["estimate_revision_usable"] is False
    assert row["decision_qualified"] is False
    assert row["revision_quarantine_reason"] == "naive_or_missing_decision_clock"


def test_flat_observation_never_gets_decision_id(tmp_path):
    for tag in ("20260506", "20260507"):
        _write_snapshot(
            tmp_path,
            tag,
            {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": 1.0}},
            mtime=datetime(2026, 5, int(tag[-2:]), 22, 0, tzinfo=timezone.utc),
        )

    row = build_revision_ledger_rows(
        load_snapshot_records(tmp_path), as_of="2026-05-07"
    )[0]

    assert row["revision_direction_prev"] == "flat"
    assert row["estimate_revision_usable"] is True
    assert row["decision_id"] is None
    assert row["decision_qualified"] is False


def test_source_switch_is_quarantined_not_called_revision(tmp_path):
    _write_snapshot(
        tmp_path,
        "20260506",
        {
            "ACME": {
                "next_earnings_date": "2026-07-30",
                "eps_estimate": 1.0,
                "eps_estimate_source": "source-a",
            }
        },
        mtime=datetime(2026, 5, 6, 22, 0, tzinfo=timezone.utc),
    )
    _write_snapshot(
        tmp_path,
        "20260507",
        {
            "ACME": {
                "next_earnings_date": "2026-07-30",
                "eps_estimate": 1.1,
                "eps_estimate_source": "source-b",
            }
        },
        mtime=datetime(2026, 5, 7, 22, 0, tzinfo=timezone.utc),
    )

    row = build_revision_ledger_rows(
        load_snapshot_records(tmp_path), as_of="2026-05-07"
    )[0]

    assert row["revision_quarantine_reason"] == "estimate_source_switch"
    assert row["decision_qualified"] is False


def test_a_to_b_to_a_rollback_is_quarantined(tmp_path):
    for tag, estimate in (("20260505", 1.0), ("20260506", 1.2), ("20260507", 1.0)):
        _write_snapshot(
            tmp_path,
            tag,
            {"ACME": {"next_earnings_date": "2026-07-30", "eps_estimate": estimate}},
            mtime=datetime(2026, 5, int(tag[-2:]), 22, 0, tzinfo=timezone.utc),
        )

    row = build_revision_ledger_rows(
        load_snapshot_records(tmp_path), as_of="2026-05-07"
    )[0]

    assert row["estimate_rollback_detected"] is True
    assert row["revision_quarantine_reason"] == "estimate_rollback_to_prior_value"
    assert row["decision_qualified"] is False
