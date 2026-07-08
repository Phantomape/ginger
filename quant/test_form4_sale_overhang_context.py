from __future__ import annotations

import json

from form4_sale_overhang_context import (
    latest_form4_sale_overhang_context_for_entry,
    persist_form4_sale_overhang_context,
    summarize_forward_reopen_progress,
)


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_form4_sale_overhang_context_is_pit_and_data_only(tmp_path):
    write_jsonl(
        tmp_path / "form4_transactions_20260628.jsonl",
        [
            {
                "ticker": "TICK",
                "usable_trade_date": "2026-06-28",
                "transaction_date": "2026-06-27",
                "accession_number": "000001",
                "owner_cik": "123",
                "owner_name": "Chief Executive",
                "transaction_code": "S",
                "acquired_disposed_code": "D",
                "shares": 10_000,
                "price": 200.0,
                "transaction_value": 2_000_000.0,
                "10b5_1_flag": True,
                "is_officer": True,
            },
            {
                "ticker": "CLEAN",
                "usable_trade_date": "2026-06-26",
                "transaction_date": "2026-06-25",
                "accession_number": "000002",
                "owner_cik": "456",
                "owner_name": "Director",
                "transaction_code": "P",
                "acquired_disposed_code": "A",
                "shares": 100,
                "price": 10.0,
                "transaction_value": 1_000.0,
                "open_market_purchase_flag": True,
            },
            {
                "ticker": "TOOFAST",
                "usable_trade_date": "2026-07-01",
                "transaction_date": "2026-06-29",
                "accession_number": "000003",
                "transaction_code": "S",
                "transaction_value": 9_000_000.0,
            },
        ],
    )
    write_jsonl(
        tmp_path / "form4_transactions_20260701.jsonl",
        [
            {
                "ticker": "FUTR",
                "usable_trade_date": "2026-06-28",
                "transaction_date": "2026-06-27",
                "accession_number": "000004",
                "transaction_code": "S",
                "transaction_value": 9_000_000.0,
            }
        ],
    )

    summary = persist_form4_sale_overhang_context(
        as_of="2026-06-29",
        data_dir=tmp_path,
        lookback_days=10,
    )

    assert summary["status"] == "ok"
    assert summary["trade_enabled"] is False
    assert summary["daily_snapshot_wired"] is True
    assert summary["production_impact"]["alters_orders"] is False
    assert summary["rows_written"] == 2
    assert summary["rows_with_high_sale_overhang"] == 1
    assert summary["source_audit"]["source_files_skipped_future"] == 1
    progress = summary["forward_reopen_progress"]
    assert progress["context_rows_current"] == 2
    assert progress["high_sale_overhang_context_rows_current"] == 1
    assert progress["closed_forward_rows_current"] == 0
    assert progress["high_sale_overhang_closed_forward_rows_current"] == 0
    assert progress["replacement_value_complete_closed_rows_current"] == 0
    assert progress["gate_ready"] is False
    assert progress["not_ready_reasons"] == [
        "closed_forward_rows_below_min",
        "high_sale_overhang_forward_rows_below_min",
    ]

    rows = load_jsonl(tmp_path / "form4_sale_overhang_context_20260629.jsonl")
    by_ticker = {row["ticker"]: row for row in rows}
    assert set(by_ticker) == {"CLEAN", "TICK"}
    assert by_ticker["TICK"]["form4_sale_overhang_bucket"] == "high_sale_overhang"
    assert by_ticker["TICK"]["form4_high_sale_overhang"] is True
    assert by_ticker["CLEAN"]["form4_sale_overhang_bucket"] == "no_sale_overhang"

    context = latest_form4_sale_overhang_context_for_entry(
        rows=rows,
        ticker="TICK",
        entry_date="2026-06-29",
    )
    assert context["eligible_for_forward_outcome_join"] is True
    assert context["form4_high_sale_overhang"] is True
    assert context["form4_latest_usable_trade_date"] == "2026-06-28"

    missing = latest_form4_sale_overhang_context_for_entry(
        rows=rows,
        ticker="MISS",
        entry_date="2026-06-29",
    )
    assert missing["eligible_for_forward_outcome_join"] is False
    assert missing["form4_sale_overhang_bucket"] == "no_pit_form4_sale_overhang_context"


def test_form4_reopen_progress_requires_closed_complete_replacement_rows():
    gate = {
        "closed_forward_rows_min": 3,
        "high_sale_overhang_forward_rows_min": 1,
        "single_ticker_share_max": 0.67,
        "required_replacement_values": ["cash", "SPY", "QQQ"],
    }
    rows = [
        {
            "ticker": "AAA",
            "form4_high_sale_overhang": True,
            "closed_forward_row": True,
            "cash_replacement_value_10d": 0.01,
            "spy_replacement_value_10d": 0.02,
            "qqq_replacement_value_10d": 0.03,
        },
        {
            "ticker": "AAA",
            "form4_high_sale_overhang": False,
            "closed_forward_row": True,
            "cash_replacement_value_10d": -0.01,
            "spy_replacement_value_10d": -0.02,
            "qqq_replacement_value_10d": -0.03,
        },
        {
            "ticker": "BBB",
            "form4_high_sale_overhang": False,
            "closed_forward_row": True,
            "cash_replacement_value_10d": 0.04,
            "spy_replacement_value_10d": 0.05,
        },
    ]

    progress = summarize_forward_reopen_progress(rows, gate=gate)

    assert progress["closed_forward_rows_current"] == 3
    assert progress["high_sale_overhang_closed_forward_rows_current"] == 1
    assert progress["replacement_value_complete_closed_rows_current"] == 2
    assert progress["closed_forward_rows_without_required_replacement_values"] == 1
    assert progress["max_single_ticker_closed_forward_row_share"] == 0.666667
    assert progress["gate_ready"] is False
    assert progress["not_ready_reasons"] == [
        "closed_forward_rows_missing_required_replacement_values"
    ]

    rows[2]["qqq_replacement_value_10d"] = 0.06
    ready = summarize_forward_reopen_progress(rows, gate=gate)
    assert ready["replacement_value_complete_closed_rows_current"] == 3
    assert ready["gate_ready"] is True
    assert ready["not_ready_reasons"] == []
