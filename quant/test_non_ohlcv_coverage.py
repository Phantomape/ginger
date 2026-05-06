from __future__ import annotations

import json
from pathlib import Path

from non_ohlcv_coverage import (
    append_manifest_record,
    build_coverage_record,
    latest_records_by_date,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_complete_day(data_root: Path, trade_date: str = "2026-05-04") -> None:
    tag = trade_date.replace("-", "")
    non_root = data_root / "non_ohlcv"
    _write_json(data_root / f"earnings_snapshot_{tag}.json", {"earnings": {"ACME": {}}})
    _write_json(data_root / f"event_snapshot_{tag}.json", {"coverage": {"event_rows_total": 1}})
    _write_json(
        non_root / f"daily_non_ohlcv_snapshot_{tag}.json",
        {
            "status": "ok",
            "sec_filing_events": {"rows_written": 1},
            "sec_filing_text": {"rows_written": 1},
            "form4_transactions": {"rows_written": 0},
        },
    )
    sec_row = {
        "ticker": "ACME",
        "form_type": "8-K",
        "accession_number": "0001-26-000001",
        "accepted_at": "2026-05-01T16:01:00",
        "usable_trade_date": trade_date,
    }
    _write_jsonl(non_root / f"sec_filing_events_{tag}.jsonl", [sec_row])
    _write_jsonl(non_root / f"sec_filing_text_{tag}.jsonl", [sec_row])
    _write_jsonl(non_root / f"form4_transactions_{tag}.jsonl", [])


def test_coverage_record_marks_complete_and_manifest_latest(tmp_path: Path) -> None:
    _write_complete_day(tmp_path)

    partial = build_coverage_record("2026-05-04", mode="catchup", data_root=tmp_path)
    partial["status"] = "partial"
    complete = build_coverage_record("2026-05-04", mode="daily", data_root=tmp_path)

    append_manifest_record(partial, data_root=tmp_path)
    append_manifest_record(complete, data_root=tmp_path)

    latest = latest_records_by_date(data_root=tmp_path)
    assert complete["status"] == "complete"
    assert latest["2026-05-04"]["status"] == "complete"
    assert latest["2026-05-04"]["mode"] == "daily"


def test_coverage_marks_sec_rows_without_accepted_datetime_as_biased(tmp_path: Path) -> None:
    _write_complete_day(tmp_path)
    tag = "20260504"
    non_root = tmp_path / "non_ohlcv"
    _write_jsonl(
        non_root / f"sec_filing_text_{tag}.jsonl",
        [
            {
                "ticker": "ACME",
                "form_type": "10-Q",
                "period_end_date": "2026-03-31",
                "usable_trade_date": "2026-05-04",
            }
        ],
    )

    record = build_coverage_record("2026-05-04", mode="backtest", data_root=tmp_path)

    assert record["status"] == "partial"
    assert record["pit_status"]["overall"] == "biased"
    assert record["pit_status"]["sec_rows_missing_accepted_at"] == 1
