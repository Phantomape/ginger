"""Tests for the Massive dividend-restart forward settlement (exp-20260803-002)."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

import massive_dividend_restart_forward_settlement as settlement_module
from massive_dividend_restart_forward_settlement import (
    entry_anchor_date,
    persist_massive_dividend_restart_forward_settlement,
)


def _weekday_sessions(start: str, end: str) -> list[str]:
    day = dt.date.fromisoformat(start)
    stop = dt.date.fromisoformat(end)
    sessions = []
    while day <= stop:
        if day.weekday() < 5:
            sessions.append(day.isoformat())
        day += dt.timedelta(days=1)
    return sessions


def _bars_db(
    tmp_path: Path,
    *,
    sessions: list[str],
    bars: dict[str, dict[str, tuple[float, float]]],
    splits: list[tuple[str, str, float, float]] = (),
    common_stocks: list[str] = (),
) -> Path:
    """bars maps ticker -> {session: (open, close)}; SPY/QQQ auto-filled flat."""

    path = tmp_path / "massive.sqlite"
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE daily_bars (ticker TEXT, trade_date TEXT, open REAL, "
        "high REAL, low REAL, close REAL, volume REAL)"
    )
    conn.execute(
        "CREATE TABLE stock_splits (ticker TEXT, execution_date TEXT, "
        "split_from REAL, split_to REAL)"
    )
    conn.execute(
        "CREATE TABLE instrument_master (ticker TEXT, instrument_type TEXT, "
        "active INTEGER)"
    )
    merged = {"SPY": {}, "QQQ": {}}
    for session in sessions:
        merged["SPY"][session] = (500.0, 500.0)
        merged["QQQ"][session] = (400.0, 400.0)
    for ticker, per_session in bars.items():
        merged.setdefault(ticker, {}).update(per_session)
    for ticker, per_session in merged.items():
        for session, (open_px, close_px) in per_session.items():
            conn.execute(
                "INSERT INTO daily_bars (ticker, trade_date, open, close, volume) "
                "VALUES (?,?,?,?,?)",
                (ticker, session, open_px, close_px, 1_000_000),
            )
    for ticker, execution_date, split_from, split_to in splits:
        conn.execute(
            "INSERT INTO stock_splits VALUES (?,?,?,?)",
            (ticker, execution_date, split_from, split_to),
        )
    for ticker in {"SPY", "QQQ", *common_stocks}:
        conn.execute("INSERT INTO instrument_master VALUES (?, 'CS', 1)", (ticker,))
    conn.commit()
    conn.close()
    return path


def _candidate(
    ticker: str,
    declaration_date: str,
    *,
    first_seen_at: str = "2026-07-06T12:00:00Z",
    gap_variant: str = "restart_after_observed_gap",
) -> dict:
    return {
        "schema_version": 1,
        "record_type": "forward_candidate",
        "decision_key": f"{ticker}:{declaration_date}",
        "ticker": ticker,
        "declaration_date": declaration_date,
        "gap_variant": gap_variant,
        "first_seen_at": first_seen_at,
        "entry_rule": (
            "first_regular_session_0930_america_new_york_open_strictly_after_"
            "first_seen_at"
        ),
        "observer_only": True,
        "trade_enabled": False,
    }


def _gate(
    ticker: str,
    declaration_date: str,
    *,
    eligible: bool = True,
    median_dollar_volume: float = 5_000_000.0,
) -> dict:
    return {
        "schema_version": 1,
        "record_type": "gate_evaluation",
        "decision_key": f"{ticker}:{declaration_date}",
        "eligible": eligible,
        "median_dollar_volume_20": median_dollar_volume,
        "observer_only": True,
        "trade_enabled": False,
    }


def _observer_dir(tmp_path: Path, rows: list[dict]) -> Path:
    root = tmp_path / "forward"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "ledger.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return root


def _core_ledger(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "position_control.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return path


def _run(
    root: Path,
    db: Path,
    core: Path,
    label: str = "20260806",
    now_utc: tuple[int, ...] = (2026, 8, 1, 1, 0),
) -> dict:
    # Default clock: 2026-07-31 21:00 ET, i.e. the evening of the last SESSIONS
    # bar, so fixtures with fresh bars stay below the stale-input threshold.
    return persist_massive_dividend_restart_forward_settlement(
        label,
        observer_dir=root,
        bars_database=db,
        position_control_ledger=core,
        now_fn=lambda: dt.datetime(*now_utc, tzinfo=dt.timezone.utc),
    )


def _events(root: Path) -> list[dict]:
    path = root / "settlement_ledger.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


SESSIONS = _weekday_sessions("2026-06-01", "2026-07-31")


class TestEntryAnchor:
    def test_before_0930_et_same_day(self):
        # 12:00 UTC == 08:00 ET during DST: same-day open is still ahead.
        assert entry_anchor_date("2026-07-06T12:00:00Z") == "2026-07-06"

    def test_at_or_after_0930_et_next_day(self):
        assert entry_anchor_date("2026-07-06T13:30:00Z") == "2026-07-07"
        assert entry_anchor_date("2026-07-06T20:00:00Z") == "2026-07-07"

    def test_cross_utc_midnight_maps_to_et_evening(self):
        # 03:32 UTC on the 7th is 23:32 ET on the 6th -> anchor next ET day.
        assert entry_anchor_date("2026-07-07T03:32:00Z") == "2026-07-07"

    def test_weekend_anchor_snaps_forward_via_calendar(self, tmp_path):
        # Saturday-seen candidate anchors Sunday; first session is Monday.
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars={"AAA": {s: (10.0, 10.0) for s in SESSIONS}},
            common_stocks=["AAA"],
        )
        root = _observer_dir(
            tmp_path,
            [
                _candidate(
                    "AAA", "2026-07-02", first_seen_at="2026-07-04T18:00:00Z"
                ),
                _gate("AAA", "2026-07-02"),
            ],
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        decisions = [e for e in _events(root) if e["record_type"] == "decision"]
        assert decisions[0]["entry_session"] == "2026-07-06"  # Monday


class TestResolutionPolicy:
    def test_pending_until_all_same_date_gates_final(self, tmp_path):
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars={"AAA": {s: (10.0, 10.0) for s in SESSIONS}},
            common_stocks=["AAA", "BBB"],
        )
        root = _observer_dir(
            tmp_path,
            [
                _candidate("AAA", "2026-07-02"),
                _candidate("BBB", "2026-07-02"),
                _gate("AAA", "2026-07-02"),
                # BBB gate evaluation still pending
            ],
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        assert summary["decision_count_total"] == 0
        assert summary["pending_declaration_date_count"] == 1

    def test_top2_liquidity_dedup_membership_and_variant_filter(self, tmp_path):
        bars = {
            t: {s: (10.0, 10.0) for s in SESSIONS}
            for t in ("AAA", "BBB", "CCC", "DDD", "EEE")
        }
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars=bars,
            common_stocks=["AAA", "BBB", "CCC", "EEE"],  # DDD fails membership
        )
        root = _observer_dir(
            tmp_path,
            [
                _candidate("AAA", "2026-07-02"),
                _candidate("BBB", "2026-07-02"),
                _candidate("CCC", "2026-07-02"),
                _candidate("DDD", "2026-07-02"),
                _candidate(
                    "EEE", "2026-07-02", gap_variant="no_prior_positive_in_provider_history"
                ),
                _gate("AAA", "2026-07-02", median_dollar_volume=9_000_000.0),
                _gate("BBB", "2026-07-02", median_dollar_volume=9_000_000.0),
                _gate("CCC", "2026-07-02", median_dollar_volume=2_000_000.0),
                _gate("DDD", "2026-07-02", median_dollar_volume=99_000_000.0),
                _gate("EEE", "2026-07-02", median_dollar_volume=99_000_000.0),
            ],
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        events = _events(root)
        decisions = [e for e in events if e["record_type"] == "decision"]
        # DDD excluded by membership, EEE by variant; tie AAA/BBB broken by ticker.
        assert [d["ticker"] for d in decisions] == ["AAA", "BBB"]
        assert [d["ordinal_within_declaration_date"] for d in decisions] == [1, 2]
        resolution = next(e for e in events if e["record_type"] == "date_resolution")
        assert resolution["membership_gate_failed_keys"] == ["DDD:2026-07-02"]
        assert resolution["selected_decision_keys"] == [
            "AAA:2026-07-02",
            "BBB:2026-07-02",
        ]

    def test_pending_until_calendar_reaches_entry_anchor(self, tmp_path):
        short_sessions = _weekday_sessions("2026-06-01", "2026-07-03")
        db = _bars_db(
            tmp_path,
            sessions=short_sessions,
            bars={"AAA": {s: (10.0, 10.0) for s in short_sessions}},
            common_stocks=["AAA"],
        )
        root = _observer_dir(
            tmp_path,
            [
                _candidate(
                    "AAA", "2026-07-02", first_seen_at="2026-07-06T12:00:00Z"
                ),
                _gate("AAA", "2026-07-02"),
            ],
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core, now_utc=(2026, 7, 4, 1, 0))
        assert summary["status"] == "ok"
        assert summary["decision_count_total"] == 0
        assert summary["pending_declaration_date_count"] == 1

    def test_late_discovery_excluded_after_date_resolution(self, tmp_path):
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars={
                "AAA": {s: (10.0, 10.0) for s in SESSIONS},
                "ZZZ": {s: (10.0, 10.0) for s in SESSIONS},
            },
            common_stocks=["AAA", "ZZZ"],
        )
        observer_rows = [
            _candidate("AAA", "2026-07-02"),
            _gate("AAA", "2026-07-02"),
        ]
        root = _observer_dir(tmp_path, observer_rows)
        core = _core_ledger(tmp_path, [])
        first = _run(root, db, core)
        assert first["decision_count_total"] == 1
        # A provider backfill discovers ZZZ for the already-resolved date.
        with (root / "ledger.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    _candidate(
                        "ZZZ", "2026-07-02", first_seen_at="2026-07-10T12:00:00Z"
                    )
                )
                + "\n"
            )
            handle.write(json.dumps(_gate("ZZZ", "2026-07-02")) + "\n")
        second = _run(root, db, core)
        assert second["late_discovery_excluded_count"] == 1
        assert second["decision_count_total"] == 1
        excluded = [
            e
            for e in _events(root)
            if e["record_type"] == "late_discovery_excluded"
        ]
        assert excluded[0]["decision_key"] == "ZZZ:2026-07-02"


class TestComparatorBinding:
    def _base(self, tmp_path, core_rows):
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars={
                "AAA": {s: (10.0, 10.0) for s in SESSIONS},
                "BBB": {s: (20.0, 20.0) for s in SESSIONS},
                "CORE": {s: (50.0, 55.0) for s in SESSIONS},
            },
            common_stocks=["AAA", "BBB", "CORE"],
        )
        root = _observer_dir(
            tmp_path,
            [
                _candidate("AAA", "2026-07-02"),
                _candidate("BBB", "2026-07-02"),
                _gate("AAA", "2026-07-02", median_dollar_volume=9_000_000.0),
                _gate("BBB", "2026-07-02", median_dollar_volume=1_500_000.0),
            ],
        )
        core = _core_ledger(tmp_path, core_rows)
        return root, db, core

    def test_first_ordinal_consumes_core_slot_second_is_cash(self, tmp_path):
        root, db, core = self._base(
            tmp_path,
            [
                {
                    "strategy_bucket": "core",
                    "ticker": "CORE",
                    "entry_date": "2026-07-06",
                },
                # duplicate daily snapshot of the same position must not
                # create a second slot
                {
                    "strategy_bucket": "core",
                    "ticker": "CORE",
                    "entry_date": "2026-07-06",
                },
            ],
        )
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        decisions = {
            e["decision_key"]: e
            for e in _events(root)
            if e["record_type"] == "decision"
        }
        first = decisions["AAA:2026-07-02"]
        second = decisions["BBB:2026-07-02"]
        assert first["comparator"] == "core_slot"
        assert first["core_slot_id"] == "CORE:2026-07-06"
        assert first["comparator_reason"] == "matched_first_available_core_slot"
        assert second["comparator"] == "cash"
        assert second["comparator_reason"] == "additional_slot_cash"

    def test_same_ticker_collision_and_absent_surface_fall_to_cash(self, tmp_path):
        root, db, core = self._base(
            tmp_path,
            [
                {
                    "strategy_bucket": "core",
                    "ticker": "AAA",
                    "entry_date": "2026-07-06",
                }
            ],
        )
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        decisions = {
            e["decision_key"]: e
            for e in _events(root)
            if e["record_type"] == "decision"
        }
        first = decisions["AAA:2026-07-02"]
        assert first["comparator"] == "cash"
        assert first["comparator_reason"] == "same_ticker_collision_cash"
        assert first["core_slot_id"] is None

    def test_missing_core_surface_is_cash(self, tmp_path):
        root, db, _ = self._base(tmp_path, [])
        summary = _run(root, db, Path(tmp_path / "missing.jsonl"))
        assert summary["status"] == "ok"
        decisions = [
            e for e in _events(root) if e["record_type"] == "decision"
        ]
        assert all(d["comparator"] == "cash" for d in decisions)


class TestSettlementMath:
    def test_h10_split_normalized_settlement_and_secondary_legs(self, tmp_path):
        # AAA: entry open 10.0 on 2026-07-06; 2:1 split on 2026-07-10;
        # exit close (10th held session incl. entry) at raw 6.0 -> 12.0 adj.
        sessions = SESSIONS
        entry = "2026-07-06"
        idx = sessions.index(entry)
        exit_session = sessions[idx + 9]
        bars = {"AAA": {s: (10.0, 10.0) for s in sessions}}
        bars["AAA"][exit_session] = (6.0, 6.0)
        db = _bars_db(
            tmp_path,
            sessions=sessions,
            bars=bars,
            splits=[("AAA", "2026-07-10", 1.0, 2.0)],
            common_stocks=["AAA"],
        )
        root = _observer_dir(
            tmp_path,
            [_candidate("AAA", "2026-07-02"), _gate("AAA", "2026-07-02")],
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        assert summary["settled_restart_decision_count"] == 1
        settlement = next(
            e for e in _events(root) if e["record_type"] == "settlement"
        )
        assert settlement["settled"] is True
        assert settlement["h10_exit_session"] == exit_session
        # gross = (6.0 * 2) / 10.0 - 1 = 0.2
        assert settlement["gross_return"] == 0.2
        assert settlement["treatment_value"] == round(4000.0 * (0.2 - 0.0035), 2)
        assert settlement["replacement_value"] == settlement["treatment_value"]
        assert settlement["spy_value"] == round(4000.0 * (0.0 - 0.0035), 2)
        assert settlement["qqq_value"] == round(4000.0 * (0.0 - 0.0035), 2)
        assert summary["reopen_progress"] == {
            "required": 30,
            "settled_restart_decisions": 1,
        }

    def test_core_slot_baseline_enters_replacement_value(self, tmp_path):
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars={
                "AAA": {s: (10.0, 11.0) for s in SESSIONS},
                "CORE": {s: (50.0, 55.0) for s in SESSIONS},
            },
            common_stocks=["AAA", "CORE"],
        )
        root = _observer_dir(
            tmp_path,
            [_candidate("AAA", "2026-07-02"), _gate("AAA", "2026-07-02")],
        )
        core = _core_ledger(
            tmp_path,
            [
                {
                    "strategy_bucket": "core",
                    "ticker": "CORE",
                    "entry_date": "2026-07-06",
                }
            ],
        )
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        settlement = next(
            e for e in _events(root) if e["record_type"] == "settlement"
        )
        treatment = 4000.0 * (11.0 / 10.0 - 1.0 - 0.0035)
        baseline = 4000.0 * (55.0 / 50.0 - 1.0 - 0.0035)
        assert settlement["comparator"] == "core_slot"
        assert settlement["baseline_value"] == round(baseline, 2)
        assert settlement["replacement_value"] == round(treatment - baseline, 2)

    def test_missing_exit_bar_voids_and_does_not_count_settled(self, tmp_path):
        entry = "2026-07-06"
        idx = SESSIONS.index(entry)
        exit_session = SESSIONS[idx + 9]
        bars = {
            "AAA": {
                s: (10.0, 10.0)
                for s in SESSIONS
                if s != exit_session  # ticker halted/delisted at exit
            }
        }
        db = _bars_db(
            tmp_path, sessions=SESSIONS, bars=bars, common_stocks=["AAA"]
        )
        root = _observer_dir(
            tmp_path,
            [_candidate("AAA", "2026-07-02"), _gate("AAA", "2026-07-02")],
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        assert summary["settled_restart_decision_count"] == 0
        assert summary["voided_decision_count"] == 1
        settlement = next(
            e for e in _events(root) if e["record_type"] == "settlement"
        )
        assert settlement["settled"] is False
        assert settlement["void_reason"] == "missing_entry_or_exit_bar"

    def test_settlement_pending_until_exit_session_in_calendar(self, tmp_path):
        sessions = _weekday_sessions("2026-06-01", "2026-07-10")
        db = _bars_db(
            tmp_path,
            sessions=sessions,
            bars={"AAA": {s: (10.0, 10.0) for s in sessions}},
            common_stocks=["AAA"],
        )
        root = _observer_dir(
            tmp_path,
            [_candidate("AAA", "2026-07-02"), _gate("AAA", "2026-07-02")],
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core, now_utc=(2026, 7, 11, 1, 0))
        assert summary["status"] == "ok"
        assert summary["decision_count_total"] == 1
        assert summary["pending_settlement_count"] == 1
        assert summary["settled_decision_count"] == 0


class TestIdempotencyAndFailClosed:
    def test_rerun_emits_no_duplicate_events(self, tmp_path):
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars={"AAA": {s: (10.0, 10.0) for s in SESSIONS}},
            common_stocks=["AAA"],
        )
        root = _observer_dir(
            tmp_path,
            [_candidate("AAA", "2026-07-02"), _gate("AAA", "2026-07-02")],
        )
        core = _core_ledger(tmp_path, [])
        first = _run(root, db, core)
        line_count = len(_events(root))
        second = _run(root, db, core)
        assert first["new_event_count"] > 0
        assert second["new_event_count"] == 0
        assert len(_events(root)) == line_count
        assert second["settled_restart_decision_count"] == 1

    def test_missing_warehouse_is_fail_closed(self, tmp_path):
        root = _observer_dir(tmp_path, [])
        core = _core_ledger(tmp_path, [])
        summary = _run(root, tmp_path / "absent.sqlite", core)
        assert summary["status"] == "blocked_missing_bars_database"
        assert summary["alert"] is True

    def test_empty_observer_ledger_is_clean_noop(self, tmp_path):
        db = _bars_db(tmp_path, sessions=SESSIONS, bars={})
        root = tmp_path / "forward"
        root.mkdir()
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        assert summary["decision_count_total"] == 0
        assert summary["new_event_count"] == 0
        assert not (root / "settlement_ledger.jsonl").is_file()

    def test_corrupt_midfile_settlement_ledger_fails_closed(self, tmp_path):
        db = _bars_db(tmp_path, sessions=SESSIONS, bars={})
        root = _observer_dir(tmp_path, [])
        (root / "settlement_ledger.jsonl").write_text(
            '{"broken\n{"schema_version": 1}\n', encoding="utf-8"
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["status"] == "error"
        assert summary["reason"] == "corrupt_ledger"
        assert summary["alert"] is True

    def test_torn_final_settlement_line_recovers_without_duplicates(self, tmp_path):
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars={"AAA": {s: (10.0, 10.0) for s in SESSIONS}},
            common_stocks=["AAA"],
        )
        root = _observer_dir(
            tmp_path,
            [_candidate("AAA", "2026-07-02"), _gate("AAA", "2026-07-02")],
        )
        core = _core_ledger(tmp_path, [])
        _run(root, db, core)
        ledger = root / "settlement_ledger.jsonl"
        intact = ledger.read_text(encoding="utf-8")
        ledger.write_text(intact + '{"torn": tru', encoding="utf-8")
        summary = _run(root, db, core)
        assert summary["status"] == "ok"
        assert summary["recovered_torn_settlement_final_line"] is True
        assert summary["new_event_count"] == 0

    def test_torn_observer_final_line_fails_closed(self, tmp_path):
        db = _bars_db(tmp_path, sessions=SESSIONS, bars={})
        root = _observer_dir(tmp_path, [])
        with (root / "ledger.jsonl").open("a", encoding="utf-8") as handle:
            handle.write('{"half":')
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["status"] == "error"
        assert summary["reason"] == "observer_ledger_torn_final_line"

    def test_stale_bars_alert_but_work_still_materializes(self, tmp_path):
        # exp-20260805-004: bars frozen at 07-31 while the clock says 08-06
        # evening (4 completed sessions later) must be alert=true non-ok, but
        # resolvable work is still settled so the alert is fail-visible, not
        # fail-stop.
        db = _bars_db(
            tmp_path,
            sessions=SESSIONS,
            bars={"AAA": {s: (10.0, 10.0) for s in SESSIONS}},
            common_stocks=["AAA"],
        )
        root = _observer_dir(
            tmp_path,
            [_candidate("AAA", "2026-07-02"), _gate("AAA", "2026-07-02")],
        )
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core, now_utc=(2026, 8, 6, 21, 0))
        assert summary["status"] == "stale_bars_input"
        assert summary["alert"] is True
        assert summary["bars_stale_sessions"] == 4
        assert summary["latest_completed_session"] == "2026-08-06"
        assert "lags latest completed session" in summary["reason"]
        assert summary["settled_restart_decision_count"] == 1

    def test_one_session_lag_stays_ok(self, tmp_path):
        # Normal intraday shape: Monday evening, Monday's grouped bars not yet
        # ingested (bars end Friday 07-31) -> exactly 1 session of lag is ok.
        db = _bars_db(tmp_path, sessions=SESSIONS, bars={})
        root = _observer_dir(tmp_path, [])
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core, now_utc=(2026, 8, 3, 21, 30))
        assert summary["status"] == "ok"
        assert summary["alert"] is False
        assert summary["bars_stale_sessions"] == 1

    def test_weekend_does_not_flap_stale_alert(self, tmp_path):
        # Sunday run after a fresh Friday close: zero sessions of lag.
        db = _bars_db(tmp_path, sessions=SESSIONS, bars={})
        root = _observer_dir(tmp_path, [])
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core, now_utc=(2026, 8, 2, 15, 0))
        assert summary["status"] == "ok"
        assert summary["alert"] is False
        assert summary["bars_stale_sessions"] == 0

    def test_count_stale_sessions_skips_holidays_and_rejects_garbage(self):
        # 2026-07-03 is the observed Independence Day holiday: from Thursday
        # 07-02 through Monday 07-06 only 07-06 itself counts as a session.
        assert (
            settlement_module.count_stale_sessions(
                "2026-07-02", dt.date(2026, 7, 6)
            )
            == 1
        )
        assert (
            settlement_module.count_stale_sessions(
                "2026-07-02", dt.date(2026, 7, 2)
            )
            == 0
        )
        assert settlement_module.count_stale_sessions(None, dt.date(2026, 7, 6)) is None
        assert (
            settlement_module.count_stale_sessions("garbage", dt.date(2026, 7, 6))
            is None
        )

    def test_summary_is_trade_disabled_observer_only(self, tmp_path):
        db = _bars_db(tmp_path, sessions=SESSIONS, bars={})
        root = _observer_dir(tmp_path, [])
        core = _core_ledger(tmp_path, [])
        summary = _run(root, db, core)
        assert summary["trade_enabled"] is False
        assert summary["observer_only"] is True
        written = json.loads(
            (root / "latest_settlement_summary.json").read_text(encoding="utf-8")
        )
        assert written["trade_enabled"] is False
