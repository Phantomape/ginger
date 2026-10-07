from __future__ import annotations

import copy
import json

from news_propagation_pair_forward_observer import (
    BORROW_COVERAGE_RULE_VERSION,
    EXPOSURE_SCHEMA_VERSION,
    OVERLAP_EXCLUSION_RULE_VERSION,
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


# exp-20260923-004: borrow-coverage contract review (forward-only exclusion).
POST_EFFECTIVE_FIRST_SEEN = "2026-09-24T03:07:00+00:00"


def _post_effective_rows():
    rows = _exposure_rows()
    for row in rows:
        row["first_seen_at"] = POST_EFFECTIVE_FIRST_SEEN
    return rows


def _post_effective_histories():
    return _borrow_histories(
        row_date="2026-09-23", archived_at="2026-09-24T03:00:00+00:00"
    )


def test_post_effective_uncovered_short_ticker_is_excluded_not_blocking():
    histories = _post_effective_histories()
    del histories["S1"]
    record = build_readiness_records(_post_effective_rows(), histories)[0]
    assert record["status"] == "measurement_ready"
    assert record["blockers"] == []
    coverage = record["borrow_coverage"]
    assert coverage["coverage_rule_version"] == BORROW_COVERAGE_RULE_VERSION
    assert coverage["required_tickers"] == 3
    assert coverage["covered_tickers"] == 2
    assert coverage["uncovered_tickers"] == [
        {"ticker": "S1", "blocker": "missing_pit_borrow"}
    ]
    assert [item["ticker"] for item in coverage["evidence"]] == ["S0", "S2"]
    assert record["pnl_measured"] is False
    assert record["trade_enabled"] is False

    # A stale ticker is excluded the same way (recorded with its kind).
    stale = _post_effective_histories()
    stale["S2"] = _borrow_histories(row_date="2026-09-15")["S2"]
    record = build_readiness_records(_post_effective_rows(), stale)[0]
    assert record["status"] == "measurement_ready"
    assert record["borrow_coverage"]["uncovered_tickers"] == [
        {"ticker": "S2", "blocker": "stale_pit_borrow"}
    ]

    # Batch-level blockers still block post-effective batches.
    rows = _post_effective_rows()
    rows[3]["exposure_ticker"] = "L0"
    record = build_readiness_records(rows, _post_effective_histories())[0]
    assert record["status"] == "blocked"
    assert "cross_side_ticker_overlap" in record["blockers"]


def test_post_effective_batch_with_no_covered_short_ticker_blocks():
    record = build_readiness_records(_post_effective_rows(), {})[0]
    assert record["status"] == "blocked"
    assert record["blockers"] == ["short_side_no_borrow_coverage"]
    assert record["borrow_coverage"]["covered_tickers"] == 0
    assert [
        item["ticker"] for item in record["borrow_coverage"]["uncovered_tickers"]
    ] == ["S0", "S1", "S2"]


def test_pre_effective_batch_keeps_frozen_v1_semantics():
    histories = _borrow_histories()
    del histories["S1"]
    record = build_readiness_records(_exposure_rows(), histories)[0]
    assert record["status"] == "blocked"
    assert "missing_pit_borrow:S1" in record["blockers"]
    assert "uncovered_tickers" not in record["borrow_coverage"]
    assert "coverage_rule_version" not in record["borrow_coverage"]
    assert set(record["borrow_coverage"]) == {
        "required_tickers",
        "covered_tickers",
        "max_age_calendar_days",
        "evidence",
        "is_broker_locate",
    }


# exp-20260924-004: cross-side-overlap contract review (forward-only exclusion).
OVERLAP_EFFECTIVE_FIRST_SEEN = "2026-09-25T03:07:00+00:00"


def _overlap_effective_rows():
    """Four tickers per side (indices 0-3 long L0..L3, 4-7 short S0..S3) so a
    single excluded ticker leaves a residual under the 40% cap."""
    rows = []
    for polarity, prefix in (("negative", "L"), ("positive", "S")):
        for index in range(4):
            rows.append(
                {
                    "schema_version": EXPOSURE_SCHEMA_VERSION,
                    "event_id": f"{polarity}-{index}",
                    "exposure_ticker": f"{prefix}{index}",
                    "event_polarity": polarity,
                    "first_seen_at": OVERLAP_EFFECTIVE_FIRST_SEEN,
                    "first_seen_batch_id": BATCH_ID,
                    "excess_5d": 99.0,
                    "excess_10d": 99.0,
                    "outcome_status": "closed",
                }
            )
    return rows


def _overlap_effective_histories(*tickers):
    histories = _borrow_histories(
        row_date="2026-09-24", archived_at="2026-09-25T03:00:00+00:00"
    )
    histories["S3"] = dict(histories["S0"])
    for ticker in tickers:
        histories[ticker] = dict(histories["S0"])
    return histories


def test_post_effective_overlap_ticker_is_excluded_not_blocking():
    rows = _overlap_effective_rows()
    rows[4]["exposure_ticker"] = "L0"  # positive-0 row now names a long ticker
    record = build_readiness_records(rows, _overlap_effective_histories("L0"))[0]
    assert record["status"] == "measurement_ready"
    assert record["blockers"] == []
    assert record["cross_side_ticker_overlap"] == ["L0"]
    exclusion = record["overlap_exclusion"]
    assert exclusion["rule_version"] == OVERLAP_EXCLUSION_RULE_VERSION
    assert exclusion["excluded_tickers"] == ["L0"]
    assert exclusion["long_side_residual"] == {
        "ticker_count": 3,
        "row_count": 3,
        "max_ticker_row_weight": 0.333333,
    }
    assert exclusion["short_side_residual"] == {
        "ticker_count": 3,
        "row_count": 3,
        "max_ticker_row_weight": 0.333333,
    }
    # Frozen side summaries still describe the full sides.
    assert record["long_side"]["tickers"] == ["L0", "L1", "L2", "L3"]
    assert record["short_side"]["tickers"] == ["L0", "S1", "S2", "S3"]
    # Borrow coverage is evaluated over the residual short side only.
    coverage = record["borrow_coverage"]
    assert coverage["coverage_rule_version"] == BORROW_COVERAGE_RULE_VERSION
    assert coverage["required_tickers"] == 3
    assert coverage["covered_tickers"] == 3
    assert [item["ticker"] for item in coverage["evidence"]] == ["S1", "S2", "S3"]
    assert coverage["uncovered_tickers"] == []
    assert record["pnl_measured"] is False
    assert record["trade_enabled"] is False

    # A post-effective batch WITHOUT overlap carries the rule marker with an
    # empty exclusion and residuals equal to the full sides.
    plain = build_readiness_records(
        _overlap_effective_rows(), _overlap_effective_histories()
    )[0]
    assert plain["status"] == "measurement_ready"
    assert plain["overlap_exclusion"]["excluded_tickers"] == []
    assert plain["overlap_exclusion"]["long_side_residual"]["ticker_count"] == 4
    assert plain["overlap_exclusion"]["short_side_residual"]["ticker_count"] == 4


def test_post_effective_side_emptied_or_concentrated_by_overlap_blocks():
    # Every short ticker also sits on the long side -> both sides empty.
    rows = _overlap_effective_rows()
    for index in range(4):
        rows[4 + index]["exposure_ticker"] = f"L{index}"
    record = build_readiness_records(
        rows, _overlap_effective_histories("L0", "L1", "L2", "L3")
    )[0]
    assert record["status"] == "blocked"
    assert record["blockers"] == [
        "long_side_emptied_by_overlap",
        "short_side_emptied_by_overlap",
    ]
    assert "cross_side_ticker_overlap" not in record["blockers"]
    assert record["overlap_exclusion"]["excluded_tickers"] == ["L0", "L1", "L2", "L3"]
    assert record["overlap_exclusion"]["short_side_residual"]["row_count"] == 0
    assert record["borrow_coverage"]["required_tickers"] == 0

    # Three of four tickers overlap -> the residual single ticker breaches the
    # 40% cap on both sides.
    rows = _overlap_effective_rows()
    for index in range(3):
        rows[4 + index]["exposure_ticker"] = f"L{index}"
    record = build_readiness_records(
        rows, _overlap_effective_histories("L0", "L1", "L2")
    )[0]
    assert record["status"] == "blocked"
    assert record["blockers"] == [
        "long_side_concentration",
        "short_side_concentration",
    ]
    assert record["overlap_exclusion"]["long_side_residual"]["max_ticker_row_weight"] == 1.0


def test_pre_effective_overlap_batch_keeps_frozen_blocker():
    # Borrow-v2 window but before the overlap rule: whole-batch blocker, no key.
    rows = _post_effective_rows()
    rows[3]["exposure_ticker"] = "L0"
    histories = _post_effective_histories()
    histories["L0"] = dict(histories["S0"])
    record = build_readiness_records(rows, histories)[0]
    assert record["status"] == "blocked"
    assert record["blockers"] == ["cross_side_ticker_overlap"]
    assert "overlap_exclusion" not in record
    assert record["borrow_coverage"]["required_tickers"] == 3

    # v1 window: identical to the frozen exp-20260826-001 semantics.
    rows = _exposure_rows()
    rows[3]["exposure_ticker"] = "L0"
    record = build_readiness_records(rows, _borrow_histories())[0]
    assert "cross_side_ticker_overlap" in record["blockers"]
    assert "overlap_exclusion" not in record
