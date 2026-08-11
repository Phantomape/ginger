import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from estimate_revision_outcomes import (  # noqa: E402
    build_estimate_revision_readiness,
    load_effective_instrument_mappings,
    materialize_estimate_revision_instrument_map,
    persist_estimate_revision_outcomes,
    persist_recent_estimate_revision_outcome_catchup,
    resolve_effective_instrument_mapping,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _create_warehouse(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute("create table ohlcv (ticker text, date text, open real, close real)")
        rows = [
            ("BKNG", "2026-06-29", 100.0, 101.0),
            ("BKNG", "2026-06-30", 101.0, 103.0),
            ("BKNG", "2026-07-01", 103.0, 104.0),
            ("BKNG", "2026-07-02", 104.0, 106.0),
            ("BKNG", "2026-07-06", 106.0, 107.0),
            ("SPY", "2026-06-29", 500.0, 501.0),
            ("SPY", "2026-06-30", 501.0, 502.0),
            ("SPY", "2026-07-01", 502.0, 503.0),
            ("SPY", "2026-07-02", 503.0, 504.0),
            ("SPY", "2026-07-06", 504.0, 505.0),
            ("QQQ", "2026-06-29", 400.0, 402.0),
            ("QQQ", "2026-06-30", 402.0, 403.0),
            ("QQQ", "2026-07-01", 403.0, 404.0),
            ("QQQ", "2026-07-02", 404.0, 406.0),
            ("QQQ", "2026-07-06", 406.0, 407.0),
        ]
        con.executemany("insert into ohlcv values (?, ?, ?, ?)", rows)
        con.commit()


def _write_instrument_map(path: Path, *, observed_at: str = "2026-06-29T19:00:00+00:00") -> None:
    _write_jsonl(
        path,
        [
            {
                "schema_version": 1,
                "mapping_id": "estimate-map:test-bkng",
                "source_ticker": "BKNG",
                "instrument_ticker": "BKNG",
                "cik": "0001075531",
                "effective_from": "2026-06-29",
                "effective_to": None,
                "observed_at": observed_at,
            }
        ],
    )


def _qualified_revision_row(**overrides) -> dict:
    row = {
        "schema_version": 3,
        "ticker": "BKNG",
        "as_of_date": "2026-06-29",
        "estimate_revision_usable": True,
        "decision_qualified": True,
        "decision_id": "estimate-revision:test-bkng",
        "decision_clock": "2026-06-29T20:00:00+00:00",
        "first_seen_at": "2026-06-29T20:00:00+00:00",
        "estimate_source": "yfinance.get_earnings_dates.EPS Estimate",
        "estimate_event_identity": "earnings:2026-07-29:unknown",
        "revision_direction_prev": "up",
        "matched_candidate_today": True,
        "matched_candidate_count": 1,
        "matched_selected_signal_count": 0,
        "matched_signal_sources": ["quant_signals"],
    }
    row.update(overrides)
    return row


def test_persist_estimate_revision_outcomes_closes_mature_h3_rows(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    ledger_path = output_dir / "estimate_revision_ledger_20260629.jsonl"
    summary_path = output_dir / "estimate_revision_ledger_summary_20260629.json"
    warehouse_path = tmp_path / "warehouse" / "warehouse_main_hot.sqlite"
    instrument_map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"

    _write_jsonl(
        ledger_path,
        [
            _qualified_revision_row(),
            {
                "ticker": "MSFT",
                "as_of_date": "2026-06-29",
                "estimate_revision_usable": True,
                "revision_direction_prev": "flat",
                "matched_candidate_today": False,
                "matched_candidate_count": 0,
            },
        ],
    )
    summary_path.write_text(
        json.dumps({"row_count": 2, "matched_candidate_rows": 1}) + "\n",
        encoding="utf-8",
    )
    _create_warehouse(warehouse_path)
    _write_instrument_map(instrument_map_path)

    summary = persist_estimate_revision_outcomes(
        as_of="2026-06-29",
        output_dir=output_dir,
        ledger_path=ledger_path,
        source_summary_path=summary_path,
        warehouse_path=warehouse_path,
        instrument_map_path=instrument_map_path,
        generated_at=datetime(2026, 7, 6, 22, tzinfo=timezone.utc),
    )

    assert summary["status"] == "ok"
    assert summary["source_ledger_row_count"] == 2
    assert summary["matched_candidate_rows"] == 1
    assert summary["usable_matched_candidate_rows"] == 1
    assert summary["nonflat_usable_matched_candidate_rows"] == 1
    assert summary["closed_rows_by_horizon"]["h0"] == 1
    assert summary["closed_rows_by_horizon"]["h1"] == 1
    assert summary["closed_rows_by_horizon"]["h3"] == 1
    assert summary["closed_rows_by_horizon"]["h5"] == 0
    assert summary["pending_rows_by_horizon"]["h5"] == 1
    assert summary["comparator_complete_rows_by_horizon"]["h3"] == 1
    assert summary["production_impact"]["alters_signal_generation"] is False
    assert summary["production_impact"]["alters_candidate_ranking"] is False
    assert summary["production_impact"]["alters_sizing"] is False
    assert summary["production_impact"]["alters_orders"] is False

    outcome_path = output_dir / "estimate_revision_outcomes_20260629.jsonl"
    summary_output_path = output_dir / "estimate_revision_outcome_summary_20260629.json"
    assert outcome_path.exists()
    assert summary_output_path.exists()
    rows = [
        json.loads(line)
        for line in outcome_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["ticker"] == "BKNG"
    assert rows[0]["entry_date"] == "2026-06-30"
    assert rows[0]["target_price"] is None
    assert rows[0]["h3_status"] == "closed"
    assert rows[0]["h3_exit_date"] == "2026-07-06"
    assert rows[0]["h3_replacement_value_vs_cash_usd"] is not None
    assert rows[0]["h3_replacement_value_vs_spy_usd"] is not None
    assert rows[0]["h3_replacement_value_vs_qqq_usd"] is not None


def test_recent_estimate_revision_outcome_catchup_refreshes_prior_ledgers(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    ledger_path = output_dir / "estimate_revision_ledger_20260629.jsonl"
    summary_path = output_dir / "estimate_revision_ledger_summary_20260629.json"
    warehouse_path = tmp_path / "warehouse" / "warehouse_main_hot.sqlite"
    instrument_map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"

    _write_jsonl(
        ledger_path,
        [_qualified_revision_row()],
    )
    summary_path.write_text(
        json.dumps({"row_count": 1, "matched_candidate_rows": 1}) + "\n",
        encoding="utf-8",
    )
    _create_warehouse(warehouse_path)
    _write_instrument_map(instrument_map_path)

    summary = persist_recent_estimate_revision_outcome_catchup(
        as_of="2026-07-06",
        output_dir=output_dir,
        warehouse_path=warehouse_path,
        instrument_map_path=instrument_map_path,
        generated_at=datetime(2026, 7, 6, 22, tzinfo=timezone.utc),
        lookback_days=10,
        exclude_dates=("2026-07-06",),
    )

    assert summary["status"] == "ok"
    assert summary["refreshed_ledger_count"] == 1
    assert summary["refreshed_ledger_dates"] == ["2026-06-29"]
    assert summary["closed_rows_by_horizon"]["h3"] == 1
    assert summary["comparator_complete_rows_by_horizon"]["h3"] == 1
    assert summary["production_impact"]["alters_orders"] is False

    outcome_path = output_dir / "estimate_revision_outcomes_20260629.jsonl"
    rows = [
        json.loads(line)
        for line in outcome_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["ticker"] == "BKNG"
    assert rows[0]["h3_status"] == "closed"


def test_naive_clock_and_missing_effective_mapping_never_settle(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    ledger_path = output_dir / "estimate_revision_ledger_20260629.jsonl"
    summary_path = output_dir / "estimate_revision_ledger_summary_20260629.json"
    warehouse_path = tmp_path / "warehouse" / "warehouse_main_hot.sqlite"
    map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"
    _write_jsonl(
        ledger_path,
        [_qualified_revision_row(decision_clock="2026-06-29T20:00:00")],
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("{}\n", encoding="utf-8")
    _create_warehouse(warehouse_path)
    _write_instrument_map(map_path)

    summary = persist_estimate_revision_outcomes(
        as_of="2026-06-29",
        output_dir=output_dir,
        ledger_path=ledger_path,
        source_summary_path=summary_path,
        warehouse_path=warehouse_path,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 7, 6, tzinfo=timezone.utc),
    )
    row = json.loads(
        (output_dir / "estimate_revision_outcomes_20260629.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )

    assert summary["status"] == "no_qualified_mapped_decisions"
    assert summary["qualified_independent_decision_count"] == 0
    assert row["settlement_qualified"] is False
    assert row["actual_entry_date"] is None
    assert row["h20_status"] == "unqualified_decision"


def test_unmatched_decision_identified_rows_settle_and_reach_readiness(tmp_path):
    """exp-20260811-001: rows with a decision identity but no candidate overlap
    must still receive settled outcome rows, otherwise the phase-2 readiness
    settled counters (over ALL qualified independent decisions) can never
    mature."""
    output_dir = tmp_path / "non_ohlcv"
    ledger_path = output_dir / "estimate_revision_ledger_20260629.jsonl"
    summary_path = output_dir / "estimate_revision_ledger_summary_20260629.json"
    warehouse_path = tmp_path / "warehouse" / "warehouse_main_hot.sqlite"
    map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"

    unmatched = _qualified_revision_row(
        decision_id="estimate-revision:unmatched-bkng",
        matched_candidate_today=False,
        matched_candidate_count=0,
        matched_signal_sources=[],
    )
    _write_jsonl(ledger_path, [unmatched])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("{}\n", encoding="utf-8")
    _write_instrument_map(map_path)

    days = []
    probe = datetime(2026, 6, 29)
    while len(days) < 25:
        if probe.weekday() < 5:
            days.append(probe.date().isoformat())
        probe += timedelta(days=1)
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(warehouse_path) as con:
        con.execute("create table ohlcv (ticker text, date text, open real, close real)")
        for ticker, base in (("BKNG", 100.0), ("SPY", 500.0), ("QQQ", 400.0)):
            con.executemany(
                "insert into ohlcv values (?, ?, ?, ?)",
                [
                    (ticker, day, base + index, base + index + 0.5)
                    for index, day in enumerate(days)
                ],
            )
        con.commit()

    summary = persist_estimate_revision_outcomes(
        as_of="2026-06-29",
        output_dir=output_dir,
        ledger_path=ledger_path,
        source_summary_path=summary_path,
        warehouse_path=warehouse_path,
        instrument_map_path=map_path,
        horizons=(5, 10, 20),
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )

    assert summary["settleable_decision_rows"] == 1
    assert summary["decision_identified_rows"] == 1
    assert summary["matched_candidate_rows"] == 0
    assert summary["closed_rows_by_horizon"]["h20"] == 1

    row = json.loads(
        (output_dir / "estimate_revision_outcomes_20260629.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert row["settlement_qualified"] is True
    assert row["h5_status"] == "closed"
    assert row["h20_status"] == "closed"

    readiness = build_estimate_revision_readiness(
        as_of="2026-08-01",
        data_dir=tmp_path,
        output_dir=output_dir,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    assert readiness["independent_decisions"] == 1
    assert readiness["settled_independent_decisions_by_horizon"] == {
        "h5": 1,
        "h10": 1,
        "h20": 1,
    }


def test_h20_settles_from_first_open_strictly_after_decision_clock(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    ledger_path = output_dir / "estimate_revision_ledger_20260629.jsonl"
    summary_path = output_dir / "estimate_revision_ledger_summary_20260629.json"
    warehouse_path = tmp_path / "warehouse" / "warehouse_main_hot.sqlite"
    map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"
    _write_jsonl(ledger_path, [_qualified_revision_row()])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("{}\n", encoding="utf-8")
    _write_instrument_map(map_path)

    days = []
    probe = datetime(2026, 6, 29)
    while len(days) < 25:
        if probe.weekday() < 5:
            days.append(probe.date().isoformat())
        probe += timedelta(days=1)
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(warehouse_path) as con:
        con.execute("create table ohlcv (ticker text, date text, open real, close real)")
        for ticker, base in (("BKNG", 100.0), ("SPY", 500.0), ("QQQ", 400.0)):
            con.executemany(
                "insert into ohlcv values (?, ?, ?, ?)",
                [
                    (ticker, day, base + index, base + index + 0.5)
                    for index, day in enumerate(days)
                ],
            )
        con.commit()

    summary = persist_estimate_revision_outcomes(
        as_of="2026-06-29",
        output_dir=output_dir,
        ledger_path=ledger_path,
        source_summary_path=summary_path,
        warehouse_path=warehouse_path,
        instrument_map_path=map_path,
        horizons=(5, 10, 20),
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    row = json.loads(
        (output_dir / "estimate_revision_outcomes_20260629.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )

    assert row["entry_date"] == "2026-06-30"
    assert row["h20_status"] == "closed"
    assert summary["closed_rows_by_horizon"]["h20"] == 1

    catchup = persist_recent_estimate_revision_outcome_catchup(
        as_of=days[-1],
        output_dir=output_dir,
        warehouse_path=warehouse_path,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    assert catchup["refreshed_ledger_count"] == 1
    assert catchup["closed_rows_by_horizon"]["h20"] == 1


def test_materialized_sec_mapping_is_forward_dated_and_idempotent(tmp_path):
    data_dir = tmp_path / "data"
    reference_dir = data_dir / "reference"
    reference_dir.mkdir(parents=True)
    (reference_dir / "sec_company_tickers.json").write_text(
        json.dumps(
            {
                "0": {"ticker": "BKNG", "cik_str": 1075531, "title": "Booking"},
                "1": {"ticker": "DUP", "cik_str": 1, "title": "One"},
                "2": {"ticker": "DUP", "cik_str": 2, "title": "Two"},
            }
        ),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.jsonl"
    target = reference_dir / "estimate_revision_instrument_map.jsonl"
    _write_jsonl(ledger, [{"ticker": "BKNG"}, {"ticker": "DUP"}, {"ticker": "MISS"}])

    first = materialize_estimate_revision_instrument_map(
        as_of="2026-07-20",
        ledger_path=ledger,
        data_dir=data_dir,
        output_path=target,
        generated_at=datetime(2026, 7, 21, 1, tzinfo=timezone.utc),
    )
    second = materialize_estimate_revision_instrument_map(
        as_of="2026-07-21",
        ledger_path=ledger,
        data_dir=data_dir,
        output_path=target,
        generated_at=datetime(2026, 7, 22, 1, tzinfo=timezone.utc),
    )
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]

    assert first["effective_from"] == "2026-07-21"
    assert first["added_mapping_count"] == 1
    assert second["added_mapping_count"] == 0
    assert len(rows) == 1
    assert rows[0]["observed_at"].endswith("+00:00")
    assert first["ambiguous_tickers"] == ["DUP"]
    assert first["missing_tickers"] == ["MISS"]


def test_cik_change_appends_supersession_and_resolves_each_decision_clock(tmp_path):
    data_dir = tmp_path / "data"
    reference_dir = data_dir / "reference"
    reference_dir.mkdir(parents=True)
    sec_path = reference_dir / "sec_company_tickers.json"
    ledger = tmp_path / "ledger.jsonl"
    target = reference_dir / "estimate_revision_instrument_map.jsonl"
    _write_jsonl(ledger, [{"ticker": "BKNG"}])
    sec_path.write_text(
        json.dumps(
            {"0": {"ticker": "BKNG", "cik_str": 1075531, "title": "Booking Old"}}
        ),
        encoding="utf-8",
    )
    materialize_estimate_revision_instrument_map(
        as_of="2026-07-21",
        ledger_path=ledger,
        data_dir=data_dir,
        output_path=target,
        generated_at=datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
    )
    original_row = json.loads(target.read_text(encoding="utf-8").splitlines()[0])

    sec_path.write_text(
        json.dumps(
            {"0": {"ticker": "BKNG", "cik_str": 9999999, "title": "Booking New"}}
        ),
        encoding="utf-8",
    )
    changed = materialize_estimate_revision_instrument_map(
        as_of="2026-08-01",
        ledger_path=ledger,
        data_dir=data_dir,
        output_path=target,
        generated_at=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )
    repeated = materialize_estimate_revision_instrument_map(
        as_of="2026-08-02",
        ledger_path=ledger,
        data_dir=data_dir,
        output_path=target,
        generated_at=datetime(2026, 8, 2, 12, tzinfo=timezone.utc),
    )
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    mappings = load_effective_instrument_mappings(target)

    assert changed["added_mapping_count"] == 1
    assert changed["superseded_mapping_count"] == 1
    assert changed["supersession_ambiguous_tickers"] == []
    assert repeated["added_mapping_count"] == 0
    assert len(rows) == 2
    assert rows[0] == original_row
    assert rows[1]["supersedes_mapping_id"] == rows[0]["mapping_id"]
    assert rows[0]["effective_to"] is None

    before_change = resolve_effective_instrument_mapping(
        {"ticker": "BKNG", "decision_clock": "2026-07-31T23:00:00+00:00"},
        mappings,
    )
    before_observation = resolve_effective_instrument_mapping(
        {"ticker": "BKNG", "decision_clock": "2026-08-01T11:59:00+00:00"},
        mappings,
    )
    after_change = resolve_effective_instrument_mapping(
        {"ticker": "BKNG", "decision_clock": "2026-08-01T12:01:00+00:00"},
        mappings,
    )

    assert before_change and before_change["cik"] == "0001075531"
    assert before_observation and before_observation["cik"] == "0001075531"
    assert after_change and after_change["cik"] == "0009999999"


def test_readiness_retro_quarantines_both_legs_of_a_b_a_chain(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"
    _write_instrument_map(map_path, observed_at="2026-06-28T00:00:00+00:00")
    first = _qualified_revision_row(
        decision_id="estimate-revision:a-to-b",
        prior_snapshot_eps_estimate=1.0,
        eps_estimate=1.2,
    )
    reversal = _qualified_revision_row(
        as_of_date="2026-06-30",
        decision_id="estimate-revision:b-to-a",
        decision_clock="2026-06-30T20:00:00+00:00",
        first_seen_at="2026-06-30T20:00:00+00:00",
        prior_snapshot_eps_estimate=1.2,
        eps_estimate=1.0,
        revision_direction_prev="down",
        decision_qualified=False,
        revision_quarantine_reason="estimate_rollback_to_prior_value",
    )
    _write_jsonl(output_dir / "estimate_revision_ledger_20260629.jsonl", [first])
    _write_jsonl(output_dir / "estimate_revision_ledger_20260630.jsonl", [reversal])
    _write_jsonl(
        output_dir / "estimate_revision_outcomes_20260629.jsonl",
        [
            {
                "decision_id": "estimate-revision:a-to-b",
                "settlement_qualified": True,
                "h5_status": "closed",
                "h10_status": "closed",
                "h20_status": "closed",
            }
        ],
    )

    readiness = build_estimate_revision_readiness(
        as_of="2026-07-21",
        data_dir=tmp_path,
        output_dir=output_dir,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )

    assert readiness["raw_rows"] == 2
    assert readiness["independent_decisions"] == 0
    assert readiness["quarantined_decisions"] == 2
    assert readiness["settled_independent_decisions"] == 0
    assert readiness["settled_independent_decisions_by_horizon"]["h20"] == 0
    assert readiness["raw_unqualified_reason_counts"] == {
        "estimate_rollback_to_prior_value": 1
    }


def test_readiness_audits_legacy_raw_rows_without_decision_ids(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    _write_jsonl(
        output_dir / "estimate_revision_ledger_20260601.jsonl",
        [
            {
                "schema_version": 2,
                "ticker": "BKNG",
                "estimate_revision_usable": True,
                "revision_direction_prev": "up",
                "decision_id": None,
            }
        ],
    )

    readiness = build_estimate_revision_readiness(
        as_of="2026-07-21",
        data_dir=tmp_path,
        output_dir=output_dir,
        generated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )

    assert readiness["raw_rows"] == 1
    assert readiness["usable_rows"] == 0
    assert readiness["quarantined_rows"] == 1
    assert readiness["raw_unqualified_reason_counts"] == {
        "legacy_snapshot_or_ledger_schema": 1
    }


def test_readiness_as_of_excludes_future_and_noncanonical_file_sets(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"
    _write_instrument_map(map_path, observed_at="2026-06-28T00:00:00+00:00")
    included_ledger = output_dir / "estimate_revision_ledger_20260629.jsonl"
    future_ledger = output_dir / "estimate_revision_ledger_20260701.jsonl"
    malformed_ledger = output_dir / "estimate_revision_ledger_latest.jsonl"
    included_outcome = output_dir / "estimate_revision_outcomes_20260629.jsonl"
    future_outcome = output_dir / "estimate_revision_outcomes_20260701.jsonl"
    malformed_outcome = output_dir / "estimate_revision_outcomes_latest.jsonl"
    _write_jsonl(included_ledger, [_qualified_revision_row()])
    _write_jsonl(future_ledger, [
        _qualified_revision_row(decision_id="estimate-revision:future")
    ])
    _write_jsonl(malformed_ledger, [
        _qualified_revision_row(decision_id="estimate-revision:malformed")
    ])
    closed = {
        "decision_id": "estimate-revision:test-bkng",
        "settlement_qualified": True,
        "h5_status": "closed",
        "h5_exit_date": "2026-06-20",
        "h10_status": "closed",
        "h10_exit_date": "2026-06-25",
        "h20_status": "closed",
        "h20_exit_date": "2026-06-29",
    }
    _write_jsonl(included_outcome, [closed])
    _write_jsonl(future_outcome, [{**closed, "decision_id": "estimate-revision:future"}])
    _write_jsonl(malformed_outcome, [
        {**closed, "decision_id": "estimate-revision:malformed"}
    ])

    first = build_estimate_revision_readiness(
        as_of="2026-06-29",
        data_dir=tmp_path,
        output_dir=output_dir,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 6, 29, 23, tzinfo=timezone.utc),
    )
    first_commitments = dict(first["artifact_commitments"])
    _write_jsonl(future_ledger, [
        _qualified_revision_row(decision_id="estimate-revision:future-mutated")
    ])
    _write_jsonl(malformed_outcome, [
        {**closed, "decision_id": "estimate-revision:malformed-mutated"}
    ])
    second = build_estimate_revision_readiness(
        as_of="2026-06-29",
        data_dir=tmp_path,
        output_dir=output_dir,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 6, 29, 23, 1, tzinfo=timezone.utc),
    )

    assert first["raw_rows"] == 1
    assert first["independent_decisions"] == 1
    assert first["ledger_file_count"] == 1
    assert first["outcome_file_count"] == 1
    assert first["outcome_row_count"] == 1
    assert first["settled_independent_decisions_by_horizon"] == {
        "h5": 1,
        "h10": 1,
        "h20": 1,
    }
    assert set(first["excluded_ledger_files"]) == {
        str(future_ledger).replace("\\", "/"),
        str(malformed_ledger).replace("\\", "/"),
    }
    assert set(first["excluded_outcome_files"]) == {
        str(future_outcome).replace("\\", "/"),
        str(malformed_outcome).replace("\\", "/"),
    }
    assert second["artifact_commitments"] == first_commitments


def test_readiness_uses_one_fail_closed_decision_qualification(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"
    _write_instrument_map(map_path, observed_at="2026-06-28T00:00:00+00:00")
    rows = [
        _qualified_revision_row(decision_qualified=False),
        _qualified_revision_row(
            decision_id="estimate-revision:legacy", schema_version=2
        ),
        _qualified_revision_row(
            decision_id="estimate-revision:unusable",
            estimate_revision_usable=False,
        ),
        _qualified_revision_row(
            decision_id="estimate-revision:naive",
            decision_clock="2026-06-29T20:00:00",
        ),
        _qualified_revision_row(
            decision_id="estimate-revision:flat",
            revision_direction_prev="flat",
        ),
        _qualified_revision_row(
            decision_id="estimate-revision:unmapped", ticker="MSFT"
        ),
        _qualified_revision_row(
            decision_id="estimate-revision:quarantined",
            revision_quarantine_reason="estimate_source_switch",
        ),
    ]
    _write_jsonl(output_dir / "estimate_revision_ledger_20260629.jsonl", rows)

    readiness = build_estimate_revision_readiness(
        as_of="2026-06-29",
        data_dir=tmp_path,
        output_dir=output_dir,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 6, 29, 23, tzinfo=timezone.utc),
    )

    # The stale redundant flag cannot veto canonical evidence, while every
    # required evidence defect fails closed.
    assert readiness["independent_decisions"] == 1
    assert readiness["mapped_tickers"] == ["BKNG"]
    assert readiness["quarantined_decisions"] == 6
    assert readiness["quarantine_reason_counts"] == {
        "estimate_source_switch": 1,
        "flat_or_missing_revision_direction": 1,
        "legacy_snapshot_or_ledger_schema": 1,
        "missing_effective_instrument_mapping": 1,
        "naive_or_missing_decision_clock": 1,
        "unqualified_revision_observation": 1,
    }


def test_readiness_as_of_uses_market_date_for_utc_evening_clock(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"
    _write_instrument_map(map_path, observed_at="2026-07-20T00:00:00+00:00")
    _write_jsonl(
        output_dir / "estimate_revision_ledger_20260721.jsonl",
        [
            _qualified_revision_row(
                as_of_date="2026-07-21",
                decision_id="estimate-revision:same-market-date",
                decision_clock="2026-07-22T01:00:00+00:00",
                first_seen_at="2026-07-22T01:00:00+00:00",
            ),
            _qualified_revision_row(
                as_of_date="2026-07-21",
                decision_id="estimate-revision:next-market-date",
                decision_clock="2026-07-22T05:00:00+00:00",
                first_seen_at="2026-07-22T05:00:00+00:00",
            ),
        ],
    )

    readiness = build_estimate_revision_readiness(
        as_of="2026-07-21",
        data_dir=tmp_path,
        output_dir=output_dir,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 7, 22, 6, tzinfo=timezone.utc),
    )

    assert readiness["independent_decisions"] == 1
    assert readiness["quarantined_decisions"] == 1
    assert readiness["quarantine_reason_counts"] == {
        "decision_clock_after_as_of": 1
    }


def test_readiness_merges_duplicate_annotations_without_replacing_identity(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    map_path = tmp_path / "reference" / "estimate_revision_instrument_map.jsonl"
    _write_jsonl(
        map_path,
        [
            {
                "schema_version": 1,
                "mapping_id": "estimate-map:test-bkng",
                "source_ticker": "BKNG",
                "instrument_ticker": "BKNG",
                "cik": "0001075531",
                "effective_from": "2026-06-28",
                "effective_to": None,
                "observed_at": "2026-06-28T00:00:00+00:00",
            },
            {
                "schema_version": 1,
                "mapping_id": "estimate-map:test-msft",
                "source_ticker": "MSFT",
                "instrument_ticker": "MSFT",
                "cik": "0000789019",
                "effective_from": "2026-06-28",
                "effective_to": None,
                "observed_at": "2026-06-28T00:00:00+00:00",
            },
        ],
    )
    canonical = _qualified_revision_row(
        matched_candidate_today=False,
        matched_candidate_count=0,
        matched_selected_signal_today=False,
        matched_selected_signal_count=0,
        matched_signal_records=[],
    )
    annotated_duplicate = _qualified_revision_row(
        ticker="MSFT",
        as_of_date="2026-06-30",
        matched_selected_signal_today=True,
        matched_selected_signal_count=1,
        matched_signal_records=[
            {"cash_conflict": True, "cash_conflict_id": "cash:test"}
        ],
    )
    substring_only = _qualified_revision_row(
        decision_id="estimate-revision:substring-only",
        as_of_date="2026-06-30",
        matched_signal_records=[
            {
                "action": "insufficient_cash",
                "reason": "no_cash_conflict",
                "cash_conflict": False,
                "cash_conflict_id": "must-not-count-without-true-flag",
            }
        ],
    )
    _write_jsonl(output_dir / "estimate_revision_ledger_20260629.jsonl", [canonical])
    _write_jsonl(
        output_dir / "estimate_revision_ledger_20260630.jsonl",
        [annotated_duplicate, substring_only],
    )

    readiness = build_estimate_revision_readiness(
        as_of="2026-06-30",
        data_dir=tmp_path,
        output_dir=output_dir,
        instrument_map_path=map_path,
        generated_at=datetime(2026, 6, 30, 23, tzinfo=timezone.utc),
    )

    assert readiness["independent_decisions"] == 2
    assert readiness["candidate_overlap_decisions"] == 2
    assert readiness["selected_signal_overlap_decisions"] == 1
    assert readiness["actual_cash_conflict_decisions"] == 1
    # The first row remains canonical despite a later duplicate carrying a
    # conflicting ticker solely to make identity replacement observable.
    assert readiness["mapped_tickers"] == ["BKNG"]
