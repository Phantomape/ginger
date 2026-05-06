from __future__ import annotations

import json
from pathlib import Path

from backfill_non_ohlcv import ensure_non_ohlcv_coverage


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_backfill_is_idempotent_and_records_existing_complete_days(tmp_path: Path) -> None:
    calls = {"earnings": 0, "daily": 0, "event": 0, "features": 0}

    def fake_earnings(start, end, universe=None, data_dir=None):
        calls["earnings"] += 1
        tag = start.replace("-", "")
        _write_json(Path(data_dir) / f"earnings_snapshot_{tag}.json", {"earnings": {"ACME": {}}})
        return [str(Path(data_dir) / f"earnings_snapshot_{tag}.json")]

    def fake_daily(**kwargs):
        calls["daily"] += 1
        day = str(kwargs["as_of"])
        tag = day.replace("-", "")
        non_root = Path(kwargs["data_dir"])
        sec_row = {
            "ticker": "ACME",
            "form_type": "8-K",
            "accession_number": "0001-26-000001",
            "accepted_at": f"{day}T16:01:00",
            "usable_trade_date": day,
        }
        _write_jsonl(non_root / f"sec_filing_events_{tag}.jsonl", [sec_row])
        _write_jsonl(non_root / f"sec_filing_text_{tag}.jsonl", [sec_row])
        _write_jsonl(non_root / f"form4_transactions_{tag}.jsonl", [])
        _write_json(
            non_root / f"daily_non_ohlcv_snapshot_{tag}.json",
            {
                "status": "ok",
                "paths": {
                    "sec_filing_text": str(non_root / f"sec_filing_text_{tag}.jsonl"),
                    "form4_transactions": str(non_root / f"form4_transactions_{tag}.jsonl"),
                },
                "sec_filing_events": {"rows_written": 1},
                "sec_filing_text": {"rows_written": 1},
                "form4_transactions": {"rows_written": 0},
            },
        )
        return {"status": "ok", "paths": {"sec_filing_text": str(non_root / f"sec_filing_text_{tag}.jsonl")}}

    def fake_event(date_key, **kwargs):
        calls["event"] += 1
        _write_json(Path(kwargs["data_dir"]) / f"event_snapshot_{date_key}.json", {"coverage": {"event_rows_total": 1}})
        return {"coverage": {"event_rows_total": 1}}

    def fake_features(date_key, **kwargs):
        calls["features"] += 1
        non_root = Path(kwargs["non_ohlcv_dir"])
        _write_jsonl(non_root / f"sec_filing_features_{date_key}.jsonl", [])
        return {"rows_written": 0}

    first = ensure_non_ohlcv_coverage(
        start="2026-05-04",
        end="2026-05-04",
        profile="backtest",
        data_root=tmp_path,
        universe=["ACME"],
        earnings_backfill_fn=fake_earnings,
        daily_snapshot_fn=fake_daily,
        event_snapshot_fn=fake_event,
        filing_features_fn=fake_features,
    )
    second = ensure_non_ohlcv_coverage(
        start="2026-05-04",
        end="2026-05-04",
        profile="backtest",
        data_root=tmp_path,
        universe=["ACME"],
        earnings_backfill_fn=fake_earnings,
        daily_snapshot_fn=fake_daily,
        event_snapshot_fn=fake_event,
        filing_features_fn=fake_features,
    )

    assert first["days_generated"] == 1
    assert second["days_generated"] == 0
    assert second["days_recorded_existing"] == 1
    assert calls == {"earnings": 1, "daily": 1, "event": 1, "features": 1}
    assert (tmp_path / "non_ohlcv" / "coverage_manifest.jsonl").exists()
    assert (tmp_path / "non_ohlcv" / "backtest_coverage_20260504_20260504.json").exists()
