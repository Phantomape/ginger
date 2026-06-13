"""Focused tests for the daily sleeve health report (exp-20260612-004)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sleeve_health as sh


def _mk_sleeve(root, name, last_asof=None):
    d = root / name
    d.mkdir(parents=True)
    if last_asof:
        (d / "snapshots.jsonl").write_text(
            json.dumps({"asof_date": last_asof}) + chr(10), encoding="utf-8"
        )
    return d


def _mk_summary_sleeve(root, name, updated_at):
    d = root / name
    d.mkdir(parents=True)
    (d / "summary.json").write_text(
        json.dumps({"updated_at": updated_at, "asof_date": updated_at[:10]}) + chr(10),
        encoding="utf-8",
    )


def test_sessions_between_skips_weekends():
    # Fri 2026-06-05 -> Thu 2026-06-11 spans one weekend: Mon..Thu = 4 sessions.
    assert sh.sessions_between("2026-06-05", "2026-06-11") == 4
    assert sh.sessions_between("2026-06-10", "2026-06-11") == 1
    assert sh.sessions_between("2026-06-11", "2026-06-11") == 0


def test_report_flags_failing_builds_and_stale_dirs(tmp_path):
    root = tmp_path / "paper_sleeves"
    _mk_sleeve(root, "fresh_sleeve", "2026-06-10")
    _mk_sleeve(root, "stale_sleeve", "2026-06-04")
    _mk_summary_sleeve(root, "summary_sleeve", "2026-06-11T05:00:00+00:00")
    _mk_summary_sleeve(root, "stale_summary_sleeve", "2026-06-04T05:00:00+00:00")
    _mk_sleeve(root, "dead_sleeve")
    payloads = {
        "fresh_sleeve_paper_sleeve": {"asof_date": "2026-06-11", "candidate_count": 1},
        "broken_paper_sleeve": {"error": "missing_sector_entries"},
        "unrelated_payload": {"error": "ignored"},
    }
    report = sh.build_sleeve_health_report(
        "2026-06-11",
        payloads,
        sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl",
    )
    assert report["failing_builds"] == ["broken_paper_sleeve"]
    assert "unrelated_payload" not in report["build_status"]
    assert report["disk_status"]["fresh_sleeve"]["status"] == "fresh"
    assert report["disk_status"]["stale_sleeve"]["status"] == "stale"
    assert report["disk_status"]["summary_sleeve"]["status"] == "fresh_summary"
    assert report["disk_status"]["summary_sleeve"]["last_summary"] == "2026-06-11"
    assert report["disk_status"]["stale_summary_sleeve"]["status"] == "stale_summary"
    assert report["disk_status"]["dead_sleeve"]["status"] == "never_persisted"
    assert report["stalled_sleeves"] == ["dead_sleeve", "stale_sleeve", "stale_summary_sleeve"]


def test_report_appends_once_per_asof(tmp_path):
    root = tmp_path / "paper_sleeves"
    _mk_sleeve(root, "fresh_sleeve", "2026-06-10")
    log = tmp_path / "health.jsonl"
    first = sh.build_sleeve_health_report("2026-06-11", {}, sleeves_root=root, health_log_path=log)
    second = sh.build_sleeve_health_report("2026-06-11", {}, sleeves_root=root, health_log_path=log)
    assert first["persisted"] is True
    assert second["persisted"] is False
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1


def test_report_is_read_only_flagged(tmp_path):
    report = sh.build_sleeve_health_report(
        "2026-06-11", {}, sleeves_root=tmp_path / "missing", health_log_path=tmp_path / "h.jsonl"
    )
    assert report["read_only"] is True
    assert report["disk_status"] == {}
