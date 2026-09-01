from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import zipfile
from datetime import date, timedelta
from pathlib import Path

from scripts import prepare_v2_pcaob_audit_amendment_stress_scout as scout


def _write_source(tmp_path: Path) -> tuple[Path, Path]:
    csv_path = tmp_path / scout.MEMBER
    columns = [
        "Form Filing ID",
        "Latest Form AP Filing",
        "Amendment Audit Report",
        "Audit Report Type",
        "Filing Date",
    ]
    rows = [
        {
            "Form Filing ID": "101",
            "Latest Form AP Filing": "false",
            "Amendment Audit Report": "true",
            "Audit Report Type": scout.AUDIT_REPORT_TYPE,
            "Filing Date": "9/4/2023 11:50:35 AM",
        },
        {
            "Form Filing ID": "102",
            "Latest Form AP Filing": "true",
            "Amendment Audit Report": "true",
            "Audit Report Type": scout.AUDIT_REPORT_TYPE,
            "Filing Date": "2023-09-05",
        },
        {
            "Form Filing ID": "103",
            "Latest Form AP Filing": "true",
            "Amendment Audit Report": "false",
            "Audit Report Type": scout.AUDIT_REPORT_TYPE,
            "Filing Date": "2023-09-06",
        },
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(csv_path, scout.MEMBER)
    member_bytes = len(csv_path.read_bytes())
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "archive_bytes": archive.stat().st_size,
                "zip_entries": [
                    {"name": scout.MEMBER, "uncompressed_bytes": member_bytes}
                ],
                "fetched_at": "2026-07-16T09:05:05Z",
            }
        ),
        encoding="utf-8",
    )
    return manifest, archive


def test_source_frame_ignores_latest_flag_and_conserves_identity(tmp_path):
    manifest, archive = _write_source(tmp_path)
    _, frame, report = scout._load_source_frame(manifest, archive)

    assert [row["form_filing_id"] for row in frame] == ["101", "102"]
    assert report["upstream_source_row_count"] == 3
    assert report["frame_row_count"] == 2
    assert len({row["source_row_id"] for row in frame}) == 2
    assert len({row["source_row_sha256"] for row in frame}) == 2


def test_calendar_preflight_never_selects_price_columns(tmp_path, monkeypatch):
    warehouse = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(warehouse)
    connection.execute(
        "CREATE TABLE ohlcv (ticker TEXT, date TEXT, open REAL, high REAL, "
        "low REAL, close REAL, volume REAL)"
    )
    connection.executemany(
        "INSERT INTO ohlcv VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("SPY", "2023-09-05", 111.0, 999.0, -999.0, 222.0, 333.0),
            ("SPY", "2023-09-06", 444.0, 999.0, -999.0, 555.0, 666.0),
        ],
    )
    connection.commit()
    connection.close()

    statements: list[str] = []
    real_connect = sqlite3.connect

    class GuardedConnection:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def execute(self, sql, params=()):
            lowered = sql.lower()
            statements.append(lowered)
            forbidden = {"open", "high", "low", "close", "volume"}
            selected = lowered.split("from", 1)[0]
            assert not any(token in selected.split() for token in forbidden)
            return self.wrapped.execute(sql, params)

        def close(self):
            self.wrapped.close()

    monkeypatch.setattr(
        scout.sqlite3,
        "connect",
        lambda *args, **kwargs: GuardedConnection(real_connect(*args, **kwargs)),
    )
    sessions, artifact = scout._load_spy_calendar(warehouse)

    assert sessions == [date(2023, 9, 5), date(2023, 9, 6)]
    assert artifact["outcome_values_read"] is False
    assert artifact["outcome_columns_read"] == []
    assert len(statements) == 1


def test_weekly_panel_freezes_next_tuesday_and_fifth_session():
    monday = date(2023, 9, 4)
    frame = [
        {
            "source_row_id": f"pcaob-form-ap:{index}",
            "filing_date": (monday + timedelta(days=index - 1)).isoformat(),
        }
        for index in range(1, 4)
    ]
    sessions = [date(2023, 9, 12) + timedelta(days=index) for index in range(8)]
    sessions = [value for value in sessions if value.weekday() < 5]

    panel = scout._decision_panel(frame, sessions)

    assert panel == [
        {
            "week_start": "2023-09-04",
            "week_end": "2023-09-10",
            "amendment_filing_count": 3,
            "cohort": "amendment_stress",
            "source_row_ids": [
                "pcaob-form-ap:1",
                "pcaob-form-ap:2",
                "pcaob-form-ap:3",
            ],
            "entry_session_date": "2023-09-12",
            "exit_session_date": "2023-09-18",
        }
    ]
