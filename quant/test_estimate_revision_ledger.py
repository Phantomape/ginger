from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from earnings_snapshot import persist_earnings_snapshot
from estimate_revision_ledger import (
    build_revision_ledger_rows,
    load_snapshot_records,
    summarize_ledger_rows,
)


def _write_snapshot(
    root: Path,
    tag: str,
    earnings: dict,
    *,
    mtime: datetime,
) -> None:
    path = root / f"earnings_snapshot_{tag}.json"
    path.write_text(
        json.dumps(
            {
                "date": tag,
                "timestamp": mtime.isoformat(),
                "earnings": earnings,
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
    assert "ignored" not in payload["earnings"]["ACME"]


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
