"""Focused tests for the daily sleeve health report (exp-20260612-004)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sleeve_health as sh


def _mk_sleeve(root, name, last_asof=None, date_key="asof_date"):
    d = root / name
    d.mkdir(parents=True)
    if last_asof:
        (d / "snapshots.jsonl").write_text(
            json.dumps({date_key: last_asof}) + chr(10), encoding="utf-8"
        )
    return d


def _mk_summary_sleeve(root, name, updated_at):
    d = root / name
    d.mkdir(parents=True)
    (d / "summary.json").write_text(
        json.dumps({"updated_at": updated_at, "asof_date": updated_at[:10]}) + chr(10),
        encoding="utf-8",
    )


def _mk_state(root, name, payload):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(json.dumps(payload) + chr(10), encoding="utf-8")


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
        "holiday_paper_sleeve": {"error": "non_us_equity_session"},
        "retired_paper_sleeve": {"error": "retired_default_off_paper_disabled"},
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


def test_report_accepts_as_of_snapshot_key(tmp_path):
    root = tmp_path / "paper_sleeves"
    _mk_sleeve(root, "core_risk_intensity_forward_observation", "2026-06-26", date_key="as_of")
    report = sh.build_sleeve_health_report(
        "2026-06-29",
        {},
        sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl",
        persist=False,
    )
    entry = report["disk_status"]["core_risk_intensity_forward_observation"]
    assert report["rule_version"] == "sleeve_health_report_v4"
    assert entry["last_snapshot"] == "2026-06-26"
    assert entry["status"] == "fresh"
    assert "core_risk_intensity_forward_observation" not in report["stalled_sleeves"]


def test_report_recognizes_latest_snapshot_json_surface(tmp_path):
    # exp-20260717-002: newer sleeves persist a single overwritten
    # latest_snapshot.json instead of appending to snapshots.jsonl; an alive
    # sleeve must not read as never_persisted.
    root = tmp_path / "paper_sleeves"
    d = root / "treasury_auction_weak_demand_tbt"
    d.mkdir(parents=True)
    (d / "latest_snapshot.json").write_text(
        json.dumps({"as_of_date": "2026-07-15", "candidate_count": 112}),
        encoding="utf-8",
    )
    stale = root / "eia_wpsr_destocking_energy_basket"
    stale.mkdir(parents=True)
    (stale / "latest_snapshot.json").write_text(
        json.dumps({"as_of_date": "2026-07-01", "candidate_count": 0}),
        encoding="utf-8",
    )
    report = sh.build_sleeve_health_report(
        "2026-07-16", {}, sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl", persist=False,
    )
    fresh_entry = report["disk_status"]["treasury_auction_weak_demand_tbt"]
    assert fresh_entry["status"] == "fresh_summary"
    assert fresh_entry["last_summary"] == "2026-07-15"
    assert fresh_entry["summary_file"] == "latest_snapshot.json"
    assert "treasury_auction_weak_demand_tbt" not in report["stalled_sleeves"]
    # A genuinely stale latest_snapshot surface is still reported with its date.
    assert report["disk_status"]["eia_wpsr_destocking_energy_basket"]["status"] == "stale_summary"
    assert "eia_wpsr_destocking_energy_basket" in report["stalled_sleeves"]


def test_report_excludes_retired_sleeves_from_stalled(tmp_path):
    # exp-20260717-002: a retired sleeve legitimately stops persisting; it must
    # not sit in stalled_sleeves forever (finra_iwm sat there 21 sessions).
    root = tmp_path / "paper_sleeves"
    _mk_sleeve(root, "finra_iwm", "2026-06-15")
    payloads = {
        "finra_iwm_paper_sleeve": {"error": "retired_default_off_paper_disabled"},
    }
    report = sh.build_sleeve_health_report(
        "2026-07-16", payloads, sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl", persist=False,
    )
    assert "finra_iwm" not in report["stalled_sleeves"]
    assert report["disk_status"]["finra_iwm"]["retired"] is True
    assert report["failing_builds"] == []


def test_report_still_flags_dateless_state_only_surface(tmp_path):
    # A sleeve persisting only a dateless, non-heartbeat state.json has no
    # verifiable freshness surface and must stay flagged.
    root = tmp_path / "paper_sleeves"
    _mk_state(root, "candidate_decision_training_ledger", {"candidate_count": 0})
    report = sh.build_sleeve_health_report(
        "2026-07-16", {}, sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl", persist=False,
    )
    assert report["disk_status"]["candidate_decision_training_ledger"]["status"] == "never_persisted"
    assert "candidate_decision_training_ledger" in report["stalled_sleeves"]


def test_report_recognizes_candidate_training_ledger_state_with_rows(tmp_path):
    root = tmp_path / "paper_sleeves"
    name = "candidate_decision_training_ledger"
    _mk_state(
        root,
        name,
        {
            "surface_contract": "append_only_candidate_decision_training_ledger",
            "as_of": "2026-07-25",
            "rows_seen": 1,
        },
    )
    (root / name / "rows.jsonl").write_text(
        json.dumps({"as_of": "2026-07-25", "ticker": "AAPL"}) + chr(10),
        encoding="utf-8",
    )
    report = sh.build_sleeve_health_report(
        "2026-07-25",
        {},
        sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl",
        persist=False,
    )
    entry = report["disk_status"][name]
    assert entry["status"] == "fresh_summary"
    assert entry["last_summary"] == "2026-07-25"
    assert entry["summary_file"] == "state.json"
    assert name not in report["stalled_sleeves"]


def test_report_rejects_unrecognized_or_incomplete_state_contracts(tmp_path):
    root = tmp_path / "paper_sleeves"
    payloads = {
        "unknown": {
            "surface_contract": "unknown_append_only_ledger",
            "as_of": "2026-07-25",
        },
        "unmarked": {"as_of": "2026-07-25"},
        "missing_rows": {
            "surface_contract": "append_only_candidate_decision_training_ledger",
            "as_of": "2026-07-25",
        },
    }
    for name, payload in payloads.items():
        _mk_state(root, name, payload)
        if name != "missing_rows":
            (root / name / "rows.jsonl").write_text("{}\n", encoding="utf-8")
    report = sh.build_sleeve_health_report(
        "2026-07-25",
        {},
        sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl",
        persist=False,
    )
    for name in payloads:
        assert report["disk_status"][name]["status"] == "never_persisted"
        assert name in report["stalled_sleeves"]


def test_report_uses_marked_heartbeat_state_when_snapshot_is_older(tmp_path):
    root = tmp_path / "paper_sleeves"
    name = "core_risk_intensity_forward_observation"
    _mk_sleeve(root, name, "2026-06-28", date_key="as_of")
    _mk_state(
        root,
        name,
        {
            "surface_contract": "forward_observation_heartbeat",
            "last_run_as_of": "2026-07-05",
            "candidate_count": 0,
            "rows_seen": 0,
        },
    )
    report = sh.build_sleeve_health_report(
        "2026-07-05",
        {},
        sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl",
        persist=False,
    )
    entry = report["disk_status"][name]
    assert entry["status"] == "fresh_summary"
    assert entry["last_snapshot"] == "2026-06-28"
    assert entry["last_summary"] == "2026-07-05"
    assert entry["summary_file"] == "state.json"
    assert name not in report["stalled_sleeves"]


def test_report_does_not_use_unmarked_state_to_mask_stale_snapshot(tmp_path):
    root = tmp_path / "paper_sleeves"
    _mk_sleeve(root, "ordinary_sleeve", "2026-06-28")
    _mk_state(root, "ordinary_sleeve", {"last_run_as_of": "2026-07-05"})
    report = sh.build_sleeve_health_report(
        "2026-07-05",
        {},
        sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl",
        persist=False,
    )
    entry = report["disk_status"]["ordinary_sleeve"]
    assert entry["status"] == "stale"
    assert entry["last_snapshot"] == "2026-06-28"
    assert "ordinary_sleeve" in report["stalled_sleeves"]


def test_report_is_read_only_flagged(tmp_path):
    report = sh.build_sleeve_health_report(
        "2026-06-11", {}, sleeves_root=tmp_path / "missing", health_log_path=tmp_path / "h.jsonl"
    )
    assert report["read_only"] is True
    assert report["disk_status"] == {}


def _mk_fire_rate_sleeve(root, name, admissions_by_asof):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"asof_date": asof, "new_pending_count": count})
        for asof, count in sorted(admissions_by_asof.items())
    ]
    (d / "snapshots.jsonl").write_text(
        chr(10).join(lines) + chr(10), encoding="utf-8"
    )


def _weekday_dates(start, n):
    import datetime

    day = datetime.date.fromisoformat(start)
    out = []
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day.isoformat())
        day += datetime.timedelta(days=1)
    return out


def test_fire_rate_watch_flags_zero_fire_against_replay_rate(tmp_path):
    root = tmp_path / "paper_sleeves"
    days = _weekday_dates("2026-05-04", 30)
    # 30 observed days at 0.2/day -> expected 6.0; zero admissions is
    # Poisson-improbable and must alert.
    _mk_fire_rate_sleeve(root, "starving", {d: 0 for d in days})
    # Same span with admissions roughly at rate stays ok.
    healthy_counts = {d: 0 for d in days}
    for d in days[::5]:
        healthy_counts[d] = 1
    _mk_fire_rate_sleeve(root, "healthy", healthy_counts)
    contracts = {
        "starving": {"replay_daily_fire_rate": 0.2, "rate_source": "test"},
        "healthy": {"replay_daily_fire_rate": 0.2, "rate_source": "test"},
        "absent": {"replay_daily_fire_rate": 0.2, "rate_source": "test"},
    }
    watch = sh.build_fire_rate_watch(
        days[-1], sleeves_root=root, contracts=contracts
    )
    assert watch["sleeves"]["starving"]["status"] == "alert_zero_fire"
    assert watch["sleeves"]["starving"]["expected_admissions"] == 6.0
    assert watch["sleeves"]["healthy"]["status"] == "ok"
    assert watch["sleeves"]["absent"]["status"] == "no_snapshots"


def test_fire_rate_watch_dedupes_same_day_reruns_and_windows(tmp_path):
    root = tmp_path / "paper_sleeves"
    d = root / "reran"
    d.mkdir(parents=True)
    # Same asof written twice (re-run): max per date counts once.
    rows = [
        {"asof_date": "2026-06-01", "new_pending_count": 0},
        {"asof_date": "2026-06-01", "new_pending_count": 2},
        {"asof_date": "2026-06-02", "new_pending_count": 1},
        {"asof_date": "2026-06-03", "new_pending_count": 0},
    ]
    (d / "snapshots.jsonl").write_text(
        chr(10).join(json.dumps(r) for r in rows) + chr(10), encoding="utf-8"
    )
    contracts = {"reran": {"replay_daily_fire_rate": 0.5, "rate_source": "test"}}
    watch = sh.build_fire_rate_watch(
        "2026-06-03", sleeves_root=root, contracts=contracts
    )
    row = watch["sleeves"]["reran"]
    assert row["actual_admissions"] == 3
    assert row["observed_days"] == 3
    assert row["status"] == "insufficient_history"
    # Window trims to the trailing unique dates.
    trimmed = sh.build_fire_rate_watch(
        "2026-06-03", sleeves_root=root, contracts=contracts, window_unique_days=2
    )
    assert trimmed["sleeves"]["reran"]["observed_days"] == 2
    assert trimmed["sleeves"]["reran"]["actual_admissions"] == 1


def test_fire_rate_watch_severe_underfire_and_report_integration(tmp_path):
    root = tmp_path / "paper_sleeves"
    days = _weekday_dates("2026-05-04", 30)
    # Expected 6.0, actual 1 -> ratio 0.167 < 0.25 with expected >= 4 -> warn.
    counts = {d: 0 for d in days}
    counts[days[10]] = 1
    _mk_fire_rate_sleeve(root, "underfiring", counts)
    contracts = {"underfiring": {"replay_daily_fire_rate": 0.2, "rate_source": "test"}}
    watch = sh.build_fire_rate_watch(days[-1], sleeves_root=root, contracts=contracts)
    assert watch["sleeves"]["underfiring"]["status"] == "warn_severe_underfire"

    # The main report surfaces contracted sleeves through starving_sleeves.
    report = sh.build_sleeve_health_report(
        "2026-07-03",
        {},
        sleeves_root=root,
        health_log_path=tmp_path / "health.jsonl",
        persist=False,
    )
    assert "fire_rate_watch" in report
    assert set(report["fire_rate_watch"]["sleeves"]) == set(sh.FIRE_RATE_CONTRACTS)


def test_fire_rate_contracts_have_verifiable_provenance():
    for name, contract in sh.FIRE_RATE_CONTRACTS.items():
        assert contract["replay_daily_fire_rate"] > 0, name
        assert str(contract.get("rate_source", "")).startswith("exp-"), name
        assert str(contract.get("accepted_experiment", "")).startswith("exp-"), name
