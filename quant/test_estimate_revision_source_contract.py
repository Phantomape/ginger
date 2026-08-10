from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from earnings_snapshot import merge_earnings_into_snapshot, persist_earnings_snapshot
from estimate_revision_ledger import (
    annotate_rows_with_signal_matches,
    build_revision_ledger_rows,
    load_daily_signal_match_records,
    load_snapshot_records,
)


def _write_snapshot(
    root: Path,
    tag: str,
    row: dict,
    *,
    mtime: datetime,
    timestamp: str | None = None,
) -> None:
    path = root / f"earnings_snapshot_{tag}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "date": tag,
                "timestamp": timestamp or mtime.isoformat(),
                "earnings": {"ACME": row},
            }
        ),
        encoding="utf-8",
    )
    seconds = mtime.timestamp()
    os.utime(path, (seconds, seconds))


def _dated_estimate(value: float, observed_at: str | None) -> dict:
    return {
        "next_earnings_date": "2026-07-30",
        "eps_estimate": value,
        "eps_estimate_source": "yfinance.get_earnings_dates.EPS Estimate",
        "eps_estimate_event_date": "2026-07-30",
        "observed_at": observed_at,
    }


def test_generic_eps_fallback_never_inherits_calendar_date_as_event_identity(tmp_path):
    path = persist_earnings_snapshot(
        {
            "ACME": {
                "next_earnings_date": "2026-07-30",
                "eps_estimate": 1.23,
                "eps_estimate_source": "yfinance.info.forwardEps",
            }
        },
        as_of=datetime(2026, 5, 7, 22, 0, tzinfo=timezone.utc),
        base_dir=tmp_path,
    )

    row = json.loads(Path(path).read_text(encoding="utf-8"))["earnings"]["ACME"]
    assert row["next_earnings_date"] == "2026-07-30"
    assert row["eps_estimate_source"] == "yfinance.info.forwardEps"
    assert row.get("eps_estimate_event_date") is None


def test_generic_eps_without_explicit_event_identity_is_quarantined(tmp_path):
    for tag, value in (("20260506", 1.0), ("20260507", 1.1)):
        observed_at = f"2026-05-{tag[-2:]}T22:00:00+00:00"
        _write_snapshot(
            tmp_path,
            tag,
            {
                "next_earnings_date": "2026-07-30",
                "eps_estimate": value,
                "eps_estimate_source": "yfinance.info.forwardEps",
                "observed_at": observed_at,
            },
            mtime=datetime(2026, 5, int(tag[-2:]), 22, 0, tzinfo=timezone.utc),
        )

    row = build_revision_ledger_rows(
        load_snapshot_records(tmp_path), as_of="2026-05-07"
    )[0]

    assert row["estimate_event_identity"] is None
    assert row["revision_quarantine_reason"] == "missing_estimate_event_identity"
    assert row["decision_id"] is None
    assert row["decision_qualified"] is False


def test_broad_merge_stamps_own_aware_retrieval_clock(tmp_path):
    core_clock = datetime(2026, 5, 7, 20, 0, tzinfo=timezone.utc)
    broad_clock = datetime(2026, 5, 7, 23, 45, tzinfo=timezone.utc)
    persist_earnings_snapshot(
        {"CORE": _dated_estimate(1.0, None)},
        as_of=core_clock,
        base_dir=tmp_path,
    )

    path = merge_earnings_into_snapshot(
        {"BROAD": _dated_estimate(2.0, None)},
        as_of=core_clock,
        observed_at=broad_clock,
        base_dir=tmp_path,
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["timestamp"] == core_clock.isoformat()
    assert payload["earnings"]["CORE"]["observed_at"] == core_clock.isoformat(timespec="seconds")
    assert payload["earnings"]["BROAD"]["observed_at"] == broad_clock.isoformat(timespec="seconds")
    assert payload["coverage"]["tickers_with_observed_at"] == 2


def test_ledger_uses_row_clock_not_earlier_snapshot_clock(tmp_path):
    for tag, value, row_hour in (
        ("20260506", 1.0, 23),
        ("20260507", 1.1, 22),
    ):
        mtime = datetime(2026, 5, int(tag[-2:]), 23, 30, tzinfo=timezone.utc)
        _write_snapshot(
            tmp_path,
            tag,
            _dated_estimate(
                value,
                f"2026-05-{tag[-2:]}T{row_hour:02d}:15:00+00:00",
            ),
            mtime=mtime,
            timestamp=f"2026-05-{tag[-2:]}T18:00:00+00:00",
        )

    row = build_revision_ledger_rows(
        load_snapshot_records(tmp_path), as_of="2026-05-07"
    )[0]

    assert row["source_snapshot_timestamp"] == "2026-05-07T18:00:00+00:00"
    assert row["decision_clock"] == "2026-05-07T22:15:00+00:00"
    assert row["source_retrieved_at"] == row["decision_clock"]
    assert row["decision_clock_source"] == "row_observed_at"
    assert row["decision_qualified"] is True


def test_ledger_fails_closed_when_row_clock_is_missing(tmp_path):
    for tag, value in (("20260506", 1.0), ("20260507", 1.1)):
        _write_snapshot(
            tmp_path,
            tag,
            _dated_estimate(value, None),
            mtime=datetime(2026, 5, int(tag[-2:]), 22, 0, tzinfo=timezone.utc),
            timestamp=f"2026-05-{tag[-2:]}T18:00:00+00:00",
        )

    row = build_revision_ledger_rows(
        load_snapshot_records(tmp_path), as_of="2026-05-07"
    )[0]

    assert row["source_snapshot_timestamp"] == "2026-05-07T18:00:00+00:00"
    assert row["decision_clock"] is None
    assert row["source_retrieved_at"] is None
    assert row["revision_quarantine_reason"] == "naive_or_missing_decision_clock"
    assert row["decision_qualified"] is False


def test_cash_admission_observation_is_structured_candidate_match(tmp_path):
    (tmp_path / "quant_signals_20260507.json").write_text(
        json.dumps(
            {
                "cash_admission_observations": [
                    {
                        "ticker": "ACME",
                        "strategy": "breakout_long",
                        "cash_conflict": True,
                        "cash_conflict_id": "cash-conflict-001",
                        "available_cash_usd": 400.0,
                        "requested_notional_usd": 500.0,
                        "cash_source": "explicit_cash_usd",
                        "capital_block_reason": "insufficient_cash",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    matches = load_daily_signal_match_records(tmp_path, "2026-05-07")
    cash_match = next(
        item for item in matches if item["record_type"] == "cash_admission_observation"
    )
    assert cash_match["is_candidate_record"] is True
    assert cash_match["is_selected_signal"] is True
    assert cash_match["cash_conflict"] is True
    assert cash_match["cash_conflict_id"] == "cash-conflict-001"
    assert cash_match["available_cash_usd"] == 400.0
    assert cash_match["requested_notional_usd"] == 500.0

    rows = [{"ticker": "ACME"}]
    annotate_rows_with_signal_matches(rows, matches)
    assert rows[0]["matched_candidate_today"] is True
    assert rows[0]["matched_selected_signal_today"] is True
    assert rows[0]["matched_signal_records"][0]["cash_conflict"] is True
    assert rows[0]["matched_signal_records"][0]["cash_conflict_id"] == "cash-conflict-001"
    assert rows[0]["matched_signal_records"][0]["available_cash_usd"] == 400.0
    assert rows[0]["matched_signal_records"][0]["requested_notional_usd"] == 500.0
