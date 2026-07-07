import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from estimate_revision_outcomes import (  # noqa: E402
    persist_estimate_revision_outcomes,
    persist_recent_estimate_revision_outcome_catchup,
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
            ("SPY", "2026-06-29", 500.0, 501.0),
            ("SPY", "2026-06-30", 501.0, 502.0),
            ("SPY", "2026-07-01", 502.0, 503.0),
            ("SPY", "2026-07-02", 503.0, 504.0),
            ("QQQ", "2026-06-29", 400.0, 402.0),
            ("QQQ", "2026-06-30", 402.0, 403.0),
            ("QQQ", "2026-07-01", 403.0, 404.0),
            ("QQQ", "2026-07-02", 404.0, 406.0),
        ]
        con.executemany("insert into ohlcv values (?, ?, ?, ?)", rows)
        con.commit()


def test_persist_estimate_revision_outcomes_closes_mature_h3_rows(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    ledger_path = output_dir / "estimate_revision_ledger_20260629.jsonl"
    summary_path = output_dir / "estimate_revision_ledger_summary_20260629.json"
    warehouse_path = tmp_path / "warehouse" / "warehouse_main_hot.sqlite"

    _write_jsonl(
        ledger_path,
        [
            {
                "ticker": "BKNG",
                "as_of_date": "2026-06-29",
                "estimate_revision_usable": True,
                "revision_direction_prev": "up",
                "matched_candidate_today": True,
                "matched_candidate_count": 1,
                "matched_selected_signal_count": 0,
                "matched_signal_sources": ["quant_signals"],
            },
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

    summary = persist_estimate_revision_outcomes(
        as_of="2026-06-29",
        output_dir=output_dir,
        ledger_path=ledger_path,
        source_summary_path=summary_path,
        warehouse_path=warehouse_path,
        generated_at=datetime(2026, 7, 6, tzinfo=timezone.utc),
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
    assert rows[0]["entry_date"] == "2026-06-29"
    assert rows[0]["target_price"] is None
    assert rows[0]["h3_status"] == "closed"
    assert rows[0]["h3_exit_date"] == "2026-07-02"
    assert rows[0]["h3_replacement_value_vs_cash_usd"] is not None
    assert rows[0]["h3_replacement_value_vs_spy_usd"] is not None
    assert rows[0]["h3_replacement_value_vs_qqq_usd"] is not None


def test_recent_estimate_revision_outcome_catchup_refreshes_prior_ledgers(tmp_path):
    output_dir = tmp_path / "non_ohlcv"
    ledger_path = output_dir / "estimate_revision_ledger_20260629.jsonl"
    summary_path = output_dir / "estimate_revision_ledger_summary_20260629.json"
    warehouse_path = tmp_path / "warehouse" / "warehouse_main_hot.sqlite"

    _write_jsonl(
        ledger_path,
        [
            {
                "ticker": "BKNG",
                "as_of_date": "2026-06-29",
                "estimate_revision_usable": True,
                "revision_direction_prev": "up",
                "matched_candidate_today": True,
                "matched_candidate_count": 1,
                "matched_selected_signal_count": 0,
                "matched_signal_sources": ["quant_signals"],
            }
        ],
    )
    summary_path.write_text(
        json.dumps({"row_count": 1, "matched_candidate_rows": 1}) + "\n",
        encoding="utf-8",
    )
    _create_warehouse(warehouse_path)

    summary = persist_recent_estimate_revision_outcome_catchup(
        as_of="2026-07-02",
        output_dir=output_dir,
        warehouse_path=warehouse_path,
        generated_at=datetime(2026, 7, 6, tzinfo=timezone.utc),
        lookback_days=5,
        exclude_dates=("2026-07-02",),
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
