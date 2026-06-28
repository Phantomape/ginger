from __future__ import annotations

import json

from quant.platform_rs20_watch import (
    RULE_VERSION as PLATFORM_RULE_VERSION,
    WATCH_NAME as PLATFORM_WATCH_NAME,
    persist_platform_rs20_forward_watch,
)
from quant.sleeve_standard_layout import write_standard_sleeve_surfaces
from quant.sleeve_health import build_sleeve_health_report


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_write_standard_surfaces_idempotent_per_asof(tmp_path) -> None:
    sleeve_dir = tmp_path / "some_watch"
    for _ in range(2):
        result = write_standard_sleeve_surfaces(
            sleeve_dir=sleeve_dir,
            sleeve_name="SOME_WATCH",
            rule_version="v1",
            asof_date="2026-06-11",
            pending_entries=[{"ticker": "ABC"}],
            extra_snapshot_fields={"ledger_row_count": 5},
        )
    assert result["written"] is True
    assert result["appended_snapshot"] is False  # second call deduped

    state = json.loads((sleeve_dir / "state.json").read_text(encoding="utf-8"))
    assert state["sleeve"] == "SOME_WATCH"
    assert state["trade_enabled"] is False
    assert state["surface_kind"] == "observe_only_watch"
    assert state["pending_entries"] == [{"ticker": "ABC"}]
    assert state["open_positions"] == []
    assert state["closed_positions"] == []
    assert result["updated_snapshot"] is False

    rows = _read_jsonl(sleeve_dir / "snapshots.jsonl")
    assert len(rows) == 1
    assert rows[0]["asof_date"] == "2026-06-11"
    assert rows[0]["candidate_count"] == 1
    assert rows[0]["closed_position_count"] == 0
    assert rows[0]["ledger_row_count"] == 5

    changed = write_standard_sleeve_surfaces(
        sleeve_dir=sleeve_dir,
        sleeve_name="SOME_WATCH",
        rule_version="v1",
        asof_date="2026-06-11",
        pending_entries=[{"ticker": "ABC"}, {"ticker": "XYZ"}],
        extra_snapshot_fields={"ledger_row_count": 6},
    )
    assert changed["appended_snapshot"] is False
    assert changed["updated_snapshot"] is True
    rows = _read_jsonl(sleeve_dir / "snapshots.jsonl")
    assert len(rows) == 1
    assert rows[0]["candidate_count"] == 2
    assert rows[0]["pending_count"] == 2
    assert rows[0]["ledger_row_count"] == 6

    # A new asof date appends a second row.
    write_standard_sleeve_surfaces(
        sleeve_dir=sleeve_dir,
        sleeve_name="SOME_WATCH",
        rule_version="v1",
        asof_date="2026-06-12",
        pending_entries=[],
    )
    rows = _read_jsonl(sleeve_dir / "snapshots.jsonl")
    assert [row["asof_date"] for row in rows] == ["2026-06-11", "2026-06-12"]


def test_missing_asof_date_writes_nothing(tmp_path) -> None:
    result = write_standard_sleeve_surfaces(
        sleeve_dir=tmp_path / "x",
        sleeve_name="X",
        rule_version="v1",
        asof_date=None,
    )
    assert result["written"] is False
    assert not (tmp_path / "x" / "state.json").exists()


def test_platform_rs20_persist_publishes_standard_surfaces(tmp_path) -> None:
    sleeve_dir = tmp_path / "platform_rs20_no_gap"
    snapshot = {
        "asof_date": "2026-06-11",
        "candidate_count": 1,
        "platform_missed_count": 2,
        "platform_rs20_missed_count": 1,
        "no_gap_rs20_watch_count": 1,
        "candidates": [
            {
                "ticker": "NFLX",
                "signal_date": "2026-06-11",
                "decision": "scarce_slot_breakout_deferred",
                "entry_price": 100.0,
            }
        ],
    }
    result = persist_platform_rs20_forward_watch(
        snapshot,
        ledger_path=sleeve_dir / "forward_watch.jsonl",
        summary_path=sleeve_dir / "summary.json",
    )
    surfaces = result["persistence"]["standard_surfaces"]
    assert surfaces["written"] is True
    assert (sleeve_dir / "state.json").exists()
    rows = _read_jsonl(sleeve_dir / "snapshots.jsonl")
    assert rows[0]["sleeve"] == PLATFORM_WATCH_NAME
    assert rows[0]["rule_version"] == PLATFORM_RULE_VERSION
    assert rows[0]["pending_count"] == 1

    # sleeve_health now classifies the sleeve from snapshots.jsonl, not the
    # nonstandard summary surface.
    report = build_sleeve_health_report(
        "2026-06-11",
        {},
        sleeves_root=tmp_path,
        persist=False,
    )
    entry = report["disk_status"]["platform_rs20_no_gap"]
    assert entry["status"] == "fresh"
    assert entry["last_snapshot"] == "2026-06-11"
