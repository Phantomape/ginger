"""Tests for the Massive dividend-restart forward observer (exp-20260802-003)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from massive_ohlcv_backfill import FetchedPayload, MassiveError
import massive_dividend_restart_forward_observer as observer_module
from massive_dividend_restart_forward_observer import (
    detect_new_candidates,
    evaluate_pending_gates,
    fetch_dividend_page_chain,
    persist_massive_dividend_restart_forward_observer,
)


def _payload(url: str, body: dict) -> FetchedPayload:
    raw = json.dumps(body).encode("utf-8")
    return FetchedPayload(
        url=url,
        retrieved_at=dt.datetime(2026, 8, 2, 12, 0, tzinfo=dt.timezone.utc),
        status_code=200,
        raw_bytes=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        payload=body,
    )


class FakeClient:
    """Maps sanitized request URLs to canned page bodies."""

    def __init__(self, pages: dict[str, dict]):
        self.pages = dict(pages)
        self.requested: list[str] = []

    def get_json(self, url: str) -> FetchedPayload:
        self.requested.append(url)
        if url not in self.pages:
            raise MassiveError(f"unexpected url {url}")
        return _payload(url, self.pages[url])


class FailingClient:
    def get_json(self, url: str) -> FetchedPayload:
        raise MassiveError("simulated outage")


BASE_URL = "https://api.massive.com/stocks/v1/dividends?limit=5000"


def _row(ticker: str, declaration_date: str, cash="0.25", currency="USD", pid=None):
    return {
        "id": pid or f"{ticker}-{declaration_date}",
        "ticker": ticker,
        "declaration_date": declaration_date,
        "cash_amount": cash,
        "currency": currency,
        "distribution_type": "recurring",
        "frequency": 4,
    }


def _single_page_client(rows: list[dict]) -> FakeClient:
    return FakeClient({BASE_URL: {"status": "OK", "results": rows}})


def _bars_db(tmp_path: Path, *, bars: list[tuple], max_extra: str | None = None) -> Path:
    path = tmp_path / "bars.sqlite"
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE daily_bars (ticker TEXT, trade_date TEXT, open REAL, "
        "high REAL, low REAL, close REAL, volume REAL)"
    )
    conn.executemany(
        "INSERT INTO daily_bars (ticker, trade_date, close, volume) VALUES (?,?,?,?)",
        bars,
    )
    if max_extra:
        conn.execute(
            "INSERT INTO daily_bars (ticker, trade_date, close, volume) "
            "VALUES ('SPY', ?, 500.0, 1000000)",
            (max_extra,),
        )
    conn.commit()
    conn.close()
    return path


def _now_sequence(*stamps: str):
    values = [dt.datetime.fromisoformat(stamp) for stamp in stamps]

    def _next() -> dt.datetime:
        return values.pop(0) if len(values) > 1 else values[0]

    return _next


NOW = _now_sequence("2026-08-02T21:00:00+00:00")


class TestFetchChain:
    def test_multi_page_chain_and_positive_usd_filter(self):
        page2 = BASE_URL + "&cursor=abc"
        client = FakeClient(
            {
                BASE_URL: {
                    "status": "OK",
                    "results": [
                        _row("AAA", "2026-07-30"),
                        _row("BBB", "2026-07-29", cash="0"),
                        _row("CCC", "2026-07-28", currency="CAD"),
                        {"ticker": "", "declaration_date": "2026-07-27"},
                    ],
                    "next_url": page2,
                },
                page2: {
                    "status": "OK",
                    "results": [_row("DDD", "2021-01-05")],
                },
            }
        )
        chain = fetch_dividend_page_chain(client)
        assert chain["page_count"] == 2
        assert chain["positive_usd_row_count"] == 2
        assert chain["skipped_row_count"] == 3
        assert chain["max_declaration_date"] == "2026-07-30"
        assert chain["min_declaration_date"] == "2021-01-05"
        assert len(chain["content_identity"]) == 64
        assert len(chain["retrieval_provenance_identity"]) == 64
        assert [
            page["sanitized_url"] for page in chain["retrieval_provenance"]
        ] == [BASE_URL, page2]

    def test_volatile_response_metadata_changes_only_retrieval_provenance(self):
        row = _row("AAA", "2026-07-30", pid="X")
        first = FakeClient(
            {
                BASE_URL: {
                    "status": "OK",
                    "request_id": "volatile-request-a",
                    "results": [row],
                }
            }
        )
        second = FakeClient(
            {
                BASE_URL: {
                    "status": "OK",
                    "request_id": "volatile-request-b",
                    "results": [row],
                }
            }
        )
        first_chain = fetch_dividend_page_chain(first)
        second_chain = fetch_dividend_page_chain(second)
        assert first_chain["content_identity"] == second_chain["content_identity"]
        assert (
            first_chain["retrieval_provenance_identity"]
            != second_chain["retrieval_provenance_identity"]
        )

    def test_page_order_and_partition_do_not_change_decision_identity(self):
        first_row = _row("AAA", "2026-07-30", pid="A")
        second_row = _row("BBB", "2026-07-29", pid="B")
        one_page = fetch_dividend_page_chain(
            _single_page_client([first_row, second_row])
        )
        page2 = BASE_URL + "&cursor=partitioned"
        split_reordered = fetch_dividend_page_chain(
            FakeClient(
                {
                    BASE_URL: {
                        "status": "OK",
                        "results": [second_row],
                        "next_url": page2,
                    },
                    page2: {"status": "OK", "results": [first_row]},
                }
            )
        )
        assert one_page["rows"] == split_reordered["rows"]
        assert one_page["content_identity"] == split_reordered["content_identity"]
        assert (
            one_page["retrieval_provenance_identity"]
            != split_reordered["retrieval_provenance_identity"]
        )

    @pytest.mark.parametrize(
        ("field", "changed_value"),
        [
            ("id", "Y"),
            ("id", 7),
            ("ticker", "BBB"),
            ("declaration_date", "2026-07-29"),
            ("cash_amount", "0.5"),
        ],
    )
    def test_each_decision_field_changes_content_identity(self, field, changed_value):
        baseline_row = _row("AAA", "2026-07-30", cash="0.25", pid="X")
        changed_row = dict(baseline_row)
        changed_row[field] = changed_value
        baseline = fetch_dividend_page_chain(_single_page_client([baseline_row]))
        changed = fetch_dividend_page_chain(_single_page_client([changed_row]))
        assert baseline["content_identity"] != changed["content_identity"]

    def test_repeated_cursor_fails_closed(self):
        client = FakeClient(
            {
                BASE_URL: {
                    "status": "OK",
                    "results": [],
                    "next_url": BASE_URL,
                }
            }
        )
        with pytest.raises(MassiveError, match="cursor repeated"):
            fetch_dividend_page_chain(client)

    def test_page_bound_fails_closed(self):
        page2 = BASE_URL + "&cursor=abc"
        client = FakeClient(
            {
                BASE_URL: {"status": "OK", "results": [], "next_url": page2},
                page2: {"status": "OK", "results": []},
            }
        )
        with pytest.raises(MassiveError, match="page bound"):
            fetch_dividend_page_chain(client, max_pages=1)

    def test_unusable_status_fails_closed(self):
        client = _single_page_client([])
        client.pages[BASE_URL]["status"] = "ERROR"
        with pytest.raises(MassiveError, match="not usable"):
            fetch_dividend_page_chain(client)

    def test_dedupes_by_provider_id(self):
        row = _row("AAA", "2026-07-30", pid="X")
        duplicated = fetch_dividend_page_chain(_single_page_client([row, row]))
        single = fetch_dividend_page_chain(_single_page_client([row]))
        assert duplicated["positive_usd_row_count"] == 1
        assert duplicated["content_identity"] == single["content_identity"]

    def test_conflicting_provider_id_fails_closed(self):
        rows = [
            _row("AAA", "2026-07-30", cash="0.25", pid="X"),
            _row("AAA", "2026-07-30", cash="0.50", pid="X"),
        ]
        with pytest.raises(MassiveError, match="conflicting decision fields"):
            fetch_dividend_page_chain(_single_page_client(rows))

    def test_anonymous_row_multiplicity_is_retained(self):
        row = _row("AAA", "2026-07-30", pid="unused")
        row.pop("id")
        duplicated = fetch_dividend_page_chain(_single_page_client([row, row]))
        single = fetch_dividend_page_chain(_single_page_client([row]))
        assert duplicated["positive_usd_row_count"] == 2
        assert duplicated["content_identity"] != single["content_identity"]


class TestDetection:
    CHAIN = {
        "rows": [
            # restart: prior 2022-06-01 -> 2026-07-30 gap far above 1095d
            {"provider_id": "1", "ticker": "GAP", "declaration_date": "2022-06-01", "cash_amount": "0.1"},
            {"provider_id": "2", "ticker": "GAP", "declaration_date": "2026-07-30", "cash_amount": "0.1"},
            # short gap: quarterly payer
            {"provider_id": "3", "ticker": "SHORT", "declaration_date": "2026-04-20", "cash_amount": "0.2"},
            {"provider_id": "4", "ticker": "SHORT", "declaration_date": "2026-07-20", "cash_amount": "0.2"},
            # no prior anywhere, provable coverage back to 2021
            {"provider_id": "5", "ticker": "NEW", "declaration_date": "2026-07-29", "cash_amount": "0.3"},
            # old candidate outside the recency window
            {"provider_id": "6", "ticker": "OLD", "declaration_date": "2026-01-02", "cash_amount": "0.4"},
            # coverage floor witness
            {"provider_id": "7", "ticker": "FLOOR", "declaration_date": "2021-01-05", "cash_amount": "0.5"},
        ],
        "max_declaration_date": "2026-07-30",
        "min_declaration_date": "2021-01-05",
        "content_identity": "c" * 64,
    }

    def test_restart_and_no_prior_detected_short_gap_and_old_skipped(self):
        rows = detect_new_candidates(
            self.CHAIN, set(), first_seen_at="2026-08-02T21:00:00Z"
        )
        keys = [row["decision_key"] for row in rows]
        assert keys == ["GAP:2026-07-30", "NEW:2026-07-29"]
        by_key = {row["decision_key"]: row for row in rows}
        assert by_key["GAP:2026-07-30"]["gap_variant"] == "restart_after_observed_gap"
        assert by_key["GAP:2026-07-30"]["gap_days"] > 1095
        assert (
            by_key["NEW:2026-07-29"]["gap_variant"]
            == "no_prior_positive_in_provider_history"
        )
        assert all(row["trade_enabled"] is False for row in rows)
        assert all(row["record_type"] == "forward_candidate" for row in rows)

    def test_known_keys_are_idempotent(self):
        rows = detect_new_candidates(
            self.CHAIN,
            {"GAP:2026-07-30"},
            first_seen_at="2026-08-02T21:00:00Z",
        )
        assert [row["decision_key"] for row in rows] == ["NEW:2026-07-29"]

    def test_shallow_coverage_blocks_unprovable_no_prior(self):
        chain = dict(self.CHAIN)
        chain["min_declaration_date"] = "2026-01-01"
        rows = detect_new_candidates(chain, set(), first_seen_at="2026-08-02T21:00:00Z")
        keys = [row["decision_key"] for row in rows]
        assert "NEW:2026-07-29" not in keys
        assert "GAP:2026-07-30" in keys  # observed gap needs no coverage proof

    def test_empty_chain_is_empty(self):
        chain = {"rows": [], "max_declaration_date": None, "min_declaration_date": None}
        assert detect_new_candidates(chain, set(), first_seen_at="x") == []


class TestGateEvaluation:
    CANDIDATE = {
        "decision_key": "GAP:2026-07-30",
        "ticker": "GAP",
        "declaration_date": "2026-07-30",
    }

    def _liquid_bars(self):
        base = dt.date(2026, 6, 25)
        bars = []
        day = base
        while len(bars) < 25:
            if day.weekday() < 5:
                bars.append(("GAP", day.isoformat(), 10.0, 500_000.0))
            day += dt.timedelta(days=1)
        return [bar for bar in bars if bar[1] < "2026-07-30"]

    def test_pending_until_warehouse_reaches_declaration(self, tmp_path):
        db = _bars_db(tmp_path, bars=self._liquid_bars())  # max < declaration
        rows = evaluate_pending_gates(
            [self.CANDIDATE], bars_database=db, evaluated_at="e"
        )
        assert rows == []

    def test_eligible_when_liquid(self, tmp_path):
        db = _bars_db(tmp_path, bars=self._liquid_bars(), max_extra="2026-07-30")
        rows = evaluate_pending_gates(
            [self.CANDIDATE], bars_database=db, evaluated_at="e"
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["eligible"] is True
        assert row["median_dollar_volume_20"] == 5_000_000.0
        assert row["last_pre_declaration_close"] == 10.0

    def test_insufficient_bars_is_final_ineligible(self, tmp_path):
        db = _bars_db(
            tmp_path,
            bars=[("GAP", "2026-07-28", 10.0, 500_000.0)],
            max_extra="2026-07-30",
        )
        rows = evaluate_pending_gates(
            [self.CANDIDATE], bars_database=db, evaluated_at="e"
        )
        assert rows[0]["eligible"] is False
        assert rows[0]["reason"] == "insufficient_pre_declaration_bars"

    def test_price_floor_gate(self, tmp_path):
        cheap = [
            (ticker, date, 2.0, volume)
            for ticker, date, _, volume in self._liquid_bars()
        ]
        db = _bars_db(tmp_path, bars=cheap, max_extra="2026-07-30")
        rows = evaluate_pending_gates(
            [self.CANDIDATE], bars_database=db, evaluated_at="e"
        )
        assert rows[0]["eligible"] is False

    def test_missing_database_is_pending(self, tmp_path):
        rows = evaluate_pending_gates(
            [self.CANDIDATE],
            bars_database=tmp_path / "missing.sqlite",
            evaluated_at="e",
        )
        assert rows == []


class TestPersist:
    ROWS = [
        _row("GAP", "2022-06-01", pid="p1"),
        _row("GAP", "2026-07-30", pid="p2"),
        _row("FLOOR", "2021-01-05", pid="p3"),
    ]

    def _run(self, tmp_path, client=None, now="2026-08-02T21:00:00+00:00", **kwargs):
        return persist_massive_dividend_restart_forward_observer(
            "2026-08-02",
            client=client if client is not None else _single_page_client(self.ROWS),
            out_dir=tmp_path / "out",
            bars_database=tmp_path / "missing.sqlite",
            now_fn=_now_sequence(now),
            **kwargs,
        )

    def _ledger(self, tmp_path):
        path = tmp_path / "out" / "ledger.jsonl"
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_first_run_appends_candidate_and_coverage(self, tmp_path):
        summary = self._run(tmp_path)
        assert summary["status"] == "ok"
        assert summary["new_candidate_count"] == 1
        assert summary["pending_gate_count"] == 1
        rows = self._ledger(tmp_path)
        types = [row["record_type"] for row in rows]
        assert types == ["forward_candidate", "coverage"]
        assert rows[0]["decision_key"] == "GAP:2026-07-30"
        assert rows[0]["first_seen_at"].startswith("2026-08-02T21")
        assert rows[1]["status"] == "ok"
        assert rows[1]["content_identity_kind"] == observer_module.CONTENT_IDENTITY_KIND
        assert rows[1]["retrieval_provenance"]
        assert rows[1]["completed_us_equity_session"] == "2026-07-31"
        state = json.loads((tmp_path / "out" / "state.json").read_text("utf-8"))
        assert state["candidate_count_total"] == 1
        assert state["content_identity_kind"] == observer_module.CONTENT_IDENTITY_KIND

    def test_same_day_rerun_is_idempotent(self, tmp_path):
        self._run(tmp_path)
        summary = self._run(tmp_path)
        assert summary["new_candidate_count"] == 0
        assert summary["candidate_count_total"] == 1
        rows = self._ledger(tmp_path)
        candidate_rows = [
            row for row in rows if row["record_type"] == "forward_candidate"
        ]
        assert len(candidate_rows) == 1
        coverage_rows = [row for row in rows if row["record_type"] == "coverage"]
        assert len(coverage_rows) == 2

    def test_same_session_weekend_and_cross_utc_reruns_do_not_advance(self, tmp_path):
        first = self._run(tmp_path, now="2026-08-07T20:20:00+00:00")
        same_session = self._run(tmp_path, now="2026-08-07T23:59:00+00:00")
        cross_utc = self._run(tmp_path, now="2026-08-08T00:05:00+00:00")
        saturday = self._run(tmp_path, now="2026-08-08T20:20:00+00:00")
        sunday = self._run(tmp_path, now="2026-08-09T20:20:00+00:00")
        for summary in [first, same_session, cross_utc, saturday, sunday]:
            assert summary["status"] == "ok"
            assert summary["completed_us_equity_session"] == "2026-08-07"
            assert summary["consecutive_unchanged_content_sessions"] == 0

    def test_clock_regression_then_recovery_does_not_recount_session(self, tmp_path):
        self._run(tmp_path, now="2026-08-03T20:20:00+00:00")
        advanced = self._run(tmp_path, now="2026-08-04T20:20:00+00:00")
        regressed = self._run(tmp_path, now="2026-08-03T22:00:00+00:00")
        restored = self._run(tmp_path, now="2026-08-04T22:00:00+00:00")
        next_session = self._run(tmp_path, now="2026-08-05T20:20:00+00:00")

        assert advanced["consecutive_unchanged_content_sessions"] == 1
        assert regressed["completed_us_equity_session"] == "2026-08-03"
        assert regressed["consecutive_unchanged_content_sessions"] == 1
        assert restored["consecutive_unchanged_content_sessions"] == 1
        assert next_session["consecutive_unchanged_content_sessions"] == 2
        state = json.loads(
            (tmp_path / "out" / "state.json").read_text(encoding="utf-8")
        )
        assert state["last_completed_us_equity_session"] == "2026-08-05"

    def test_three_distinct_completed_sessions_unchanged_fails_closed(self, tmp_path):
        baseline = self._run(tmp_path, now="2026-08-03T20:20:00+00:00")
        first = self._run(tmp_path, now="2026-08-04T20:20:00+00:00")
        second = self._run(tmp_path, now="2026-08-05T20:20:00+00:00")
        assert baseline["consecutive_unchanged_content_sessions"] == 0
        assert first["consecutive_unchanged_content_sessions"] == 1
        assert second["consecutive_unchanged_content_sessions"] == 2
        summary = self._run(tmp_path, now="2026-08-06T20:20:00+00:00")
        assert summary["status"] == "stale_input"
        assert summary["alert"] is True
        assert summary["completed_us_equity_session"] == "2026-08-06"
        assert summary["consecutive_unchanged_content_sessions"] == 3
        assert summary["consecutive_unchanged_content_runs"] == 3
        summary = json.loads(
            (tmp_path / "out" / "latest_summary.json").read_text("utf-8")
        )
        assert summary["status"] == "stale_input"

    def test_changed_content_resets_stale_counter(self, tmp_path):
        self._run(tmp_path, now="2026-08-03T20:20:00+00:00")
        self._run(tmp_path, now="2026-08-04T20:20:00+00:00")
        self._run(tmp_path, now="2026-08-05T20:20:00+00:00")
        self._run(tmp_path, now="2026-08-06T20:20:00+00:00")
        changed = self.ROWS + [_row("NEWROW", "2026-07-31", pid="p9")]
        summary = self._run(
            tmp_path,
            client=_single_page_client(changed),
            now="2026-08-07T20:20:00+00:00",
        )
        assert summary["status"] == "ok"
        assert summary["consecutive_unchanged_content_sessions"] == 0
        assert summary["consecutive_unchanged_content_runs"] == 0

    def test_legacy_state_migrates_once_then_survives_restarts(self, tmp_path):
        self._run(tmp_path, now="2026-08-03T20:20:00+00:00")
        state_path = tmp_path / "out" / "state.json"
        legacy = json.loads(state_path.read_text(encoding="utf-8"))
        legacy.pop("content_identity_kind")
        legacy.pop("consecutive_unchanged_content_sessions")
        legacy["last_content_identity"] = "legacy-raw-page-chain-identity"
        legacy["consecutive_unchanged_content_runs"] = 99
        state_path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self._run(tmp_path, now="2026-08-04T20:20:00+00:00")
        assert migrated["status"] == "ok"
        assert migrated["legacy_state_migrated"] is True
        assert migrated["consecutive_unchanged_content_sessions"] == 0

        same_session_restart = self._run(
            tmp_path, now="2026-08-04T23:30:00+00:00"
        )
        assert same_session_restart["legacy_state_migrated"] is False
        assert same_session_restart["consecutive_unchanged_content_sessions"] == 0
        next_session_restart = self._run(
            tmp_path, now="2026-08-05T20:20:00+00:00"
        )
        assert next_session_restart["consecutive_unchanged_content_sessions"] == 1
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        assert persisted["content_identity_kind"] == observer_module.CONTENT_IDENTITY_KIND

    def test_fetch_failure_persists_error_status(self, tmp_path):
        summary = self._run(tmp_path, client=FailingClient())
        assert summary["status"] == "error"
        assert summary["alert"] is True
        rows = self._ledger(tmp_path)
        assert rows[-1]["record_type"] == "coverage"
        assert rows[-1]["status"] == "error"
        persisted = json.loads(
            (tmp_path / "out" / "latest_summary.json").read_text("utf-8")
        )
        assert persisted["status"] == "error"

    def test_corrupt_state_recovers(self, tmp_path):
        self._run(tmp_path)
        (tmp_path / "out" / "state.json").write_text("{not json", encoding="utf-8")
        summary = self._run(tmp_path)
        assert summary["status"] == "ok"
        assert summary["consecutive_unchanged_content_runs"] == 0

    def test_cross_utc_midnight_run_keeps_data_calendar_attribution(self, tmp_path):
        summary = self._run(tmp_path, now="2026-08-03T00:05:00+00:00")
        rows = self._ledger(tmp_path)
        candidate = rows[0]
        # Attribution stays on the data calendar: declaration_date from the
        # provider row, vintage from the injected clock; the run label never
        # shifts the decision key.
        assert candidate["declaration_date"] == "2026-07-30"
        assert candidate["first_seen_at"].startswith("2026-08-03T00")
        assert summary["max_declaration_date"] == "2026-07-30"

    def test_gate_evaluation_appended_when_bars_arrive(self, tmp_path):
        self._run(tmp_path)
        bars = TestGateEvaluation()._liquid_bars()
        db = _bars_db(tmp_path, bars=bars, max_extra="2026-07-30")
        summary = persist_massive_dividend_restart_forward_observer(
            "2026-08-03",
            client=_single_page_client(self.ROWS),
            out_dir=tmp_path / "out",
            bars_database=db,
            now_fn=_now_sequence("2026-08-03T21:00:00+00:00"),
        )
        assert summary["new_gate_evaluation_count"] == 1
        assert summary["eligible_candidate_count"] == 1
        assert summary["pending_gate_count"] == 0
        rows = self._ledger(tmp_path)
        gate_rows = [row for row in rows if row["record_type"] == "gate_evaluation"]
        assert len(gate_rows) == 1
        assert gate_rows[0]["eligible"] is True
        # third run: evaluation is not re-emitted
        summary = persist_massive_dividend_restart_forward_observer(
            "2026-08-04",
            client=_single_page_client(self.ROWS),
            out_dir=tmp_path / "out",
            bars_database=db,
            now_fn=_now_sequence("2026-08-04T21:00:00+00:00"),
        )
        assert summary["new_gate_evaluation_count"] == 0
        rows = self._ledger(tmp_path)
        assert (
            len([row for row in rows if row["record_type"] == "gate_evaluation"]) == 1
        )


class TestPathGuard:
    def test_continuation_leaving_dividends_path_fails_closed(self):
        rogue = "https://api.massive.com/stocks/v1/splits?limit=5000&cursor=x"
        client = FakeClient(
            {
                BASE_URL: {"status": "OK", "results": [], "next_url": rogue},
                rogue: {"status": "OK", "results": []},
            }
        )
        with pytest.raises(MassiveError, match="left the dividends path"):
            fetch_dividend_page_chain(client)
