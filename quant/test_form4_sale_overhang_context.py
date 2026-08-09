from __future__ import annotations

import hashlib
import json

from form4_sale_overhang_context import (
    aggregate_form4_sale_overhang_forward_rows,
    latest_form4_sale_overhang_context_for_entry,
    persist_form4_sale_overhang_context,
    refresh_form4_sale_overhang_forward_ledger,
    summarize_forward_reopen_progress,
)


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def candidate_decision(
    observation_id,
    *,
    ticker="AAA",
    as_of="2026-07-28",
    entry_date="2026-07-29",
):
    return {
        "record_type": "candidate_decision_snapshot",
        "rule_version": "candidate_decision_training_ledger_v1",
        "observation_id": observation_id,
        "as_of": as_of,
        "entry_date": entry_date,
        "ticker": ticker,
        "rank": 1,
        "strategy": "trend_long",
        "sector": "Technology",
        "candidate_status": "selected",
    }


def candidate_outcome(observation_id, horizon, *, ticker="AAA"):
    return {
        "record_type": "candidate_decision_outcome",
        "outcome_id": f"{observation_id}-{horizon}d",
        "observation_id": observation_id,
        "ticker": ticker,
        "horizon": f"{horizon}d",
        "horizon_trading_days": horizon,
        "entry_date": "2026-07-29",
        "exit_date": "2026-08-12" if horizon == 10 else "2026-08-26",
        "candidate_return_pct": 0.05 if horizon == 10 else 0.08,
        "spy_return_pct": 0.02,
        "qqq_return_pct": 0.03,
        "replacement_value_vs_cash_usd": 500.0 if horizon == 10 else 800.0,
        "replacement_value_vs_spy_usd": 300.0 if horizon == 10 else 600.0,
        "replacement_value_vs_qqq_usd": 200.0 if horizon == 10 else 500.0,
        "label_source": "fixed_horizon_daily_ohlcv_next_open_entry",
    }


def candidate_state_payload(ledger_path, as_of):
    raw = ledger_path.read_bytes()
    return {
        "last_run_as_of": as_of,
        "ledger_content_identity": {
            "status": "ok",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "byte_count": len(raw),
            "record_count": sum(1 for line in raw.splitlines() if line.strip()),
        },
    }


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


def test_forward_ledger_is_prospective_pit_settled_and_idempotent(tmp_path):
    data_dir = tmp_path / "non_ohlcv"
    data_dir.mkdir()
    write_jsonl(
        data_dir / "form4_transactions_20260727.jsonl",
        [
            {
                "ticker": "AAA",
                "usable_trade_date": "2026-07-27",
                "transaction_date": "2026-07-26",
                "accession_number": "aaa-sale",
                "owner_cik": "111",
                "transaction_code": "S",
                "transaction_value": 6_000_000.0,
                "is_officer": True,
            }
        ],
    )
    write_jsonl(
        data_dir / "form4_transactions_20260831.jsonl",
        [
            {
                "ticker": "HEALTH",
                "usable_trade_date": "2026-08-31",
                "transaction_date": "2026-08-30",
                "accession_number": "health-current",
                "owner_cik": "222",
                "transaction_code": "P",
                "transaction_value": 2_000.0,
                "open_market_purchase_flag": True,
            },
        ],
    )
    for snapshot_day in (
        "2026-07-28",
        "2026-07-29",
        "2026-07-30",
        "2026-08-31",
    ):
        summary = persist_form4_sale_overhang_context(
            as_of=snapshot_day,
            data_dir=data_dir,
        )
        assert summary["content_identity"]["sha256"]

    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    candidate_ledger = candidate_dir / "rows.jsonl"
    candidate_state = candidate_dir / "state.json"
    pre_effective_id = "pre-effective"
    prospective_id = "prospective"
    write_jsonl(
        candidate_ledger,
        [
            candidate_decision(
                pre_effective_id,
                as_of="2026-07-27",
                entry_date="2026-07-28",
            ),
            candidate_decision(prospective_id),
            candidate_outcome(pre_effective_id, 10),
            candidate_outcome(pre_effective_id, 20),
            candidate_outcome(prospective_id, 10),
            candidate_outcome(prospective_id, 20),
        ],
    )
    candidate_state.write_text(
        json.dumps(candidate_state_payload(candidate_ledger, "2026-08-31")),
        encoding="utf-8",
    )
    forward_ledger = tmp_path / "forward" / "rows.jsonl"

    first = refresh_form4_sale_overhang_forward_ledger(
        as_of="2026-08-31",
        candidate_ledger_path=candidate_ledger,
        candidate_state_path=candidate_state,
        data_dir=data_dir,
        ledger_path=forward_ledger,
        effective_date="2026-07-28",
    )
    second = refresh_form4_sale_overhang_forward_ledger(
        as_of="2026-08-31",
        candidate_ledger_path=candidate_ledger,
        candidate_state_path=candidate_state,
        data_dir=data_dir,
        ledger_path=forward_ledger,
        effective_date="2026-07-28",
    )

    assert first["status"] == "ok"
    assert first["health"]["fail_closed"] is False
    assert first["decision_rows_seen"] == 2
    assert first["eligible_decision_rows_seen"] == 1
    assert first["decision_rows_written"] == 1
    assert first["outcome_rows_written"] == 2
    assert first["append_skip_reasons"]["pre_effective_decision_excluded"] == 1
    assert second["decision_rows_written"] == 0
    assert second["outcome_rows_written"] == 0

    records = load_jsonl(forward_ledger)
    decisions = [
        row
        for row in records
        if row["record_type"] == "form4_sale_overhang_forward_decision"
    ]
    assert len(decisions) == 1
    assert decisions[0]["source_observation_id"] == prospective_id
    assert decisions[0]["form4_context_as_of"] == "2026-07-29"
    assert decisions[0]["form4_latest_usable_trade_date"] == "2026-07-27"
    assert decisions[0]["prospective_forward_evidence"] is True

    aggregate = aggregate_form4_sale_overhang_forward_rows(records)
    assert len(aggregate) == 1
    assert aggregate[0]["closed_forward_row"] is True
    assert aggregate[0]["complete_outcome_horizons"] == ["10d", "20d"]
    assert aggregate[0]["cash_replacement_value_10d"] == 500.0
    assert aggregate[0]["spy_replacement_value_20d"] == 600.0
    assert aggregate[0]["qqq_replacement_value_20d"] == 500.0
    progress = first["forward_reopen_progress"]
    assert progress["closed_forward_rows_current"] == 1
    assert progress["high_sale_overhang_closed_forward_rows_current"] == 1
    assert progress["replacement_value_complete_closed_rows_current"] == 1
    assert progress["observer_health_status"] == "ok"


def test_forward_ledger_health_fails_closed_for_missing_or_stale_producer(tmp_path):
    data_dir = tmp_path / "non_ohlcv"
    data_dir.mkdir()
    write_jsonl(
        data_dir / "form4_transactions_20260728.jsonl",
        [
            {
                "ticker": "AAA",
                "usable_trade_date": "2026-07-28",
                "transaction_date": "2026-07-27",
                "accession_number": "aaa-current",
                "owner_cik": "111",
                "transaction_code": "S",
                "transaction_value": 6_000_000.0,
            }
        ],
    )
    persist_form4_sale_overhang_context(as_of="2026-07-28", data_dir=data_dir)
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    candidate_ledger = candidate_dir / "rows.jsonl"
    write_jsonl(candidate_ledger, [candidate_decision("prospective")])
    forward_ledger = tmp_path / "forward" / "rows.jsonl"

    missing = refresh_form4_sale_overhang_forward_ledger(
        as_of="2026-07-28",
        candidate_ledger_path=candidate_ledger,
        data_dir=data_dir,
        ledger_path=forward_ledger,
    )
    assert missing["status"] == "unavailable"
    assert missing["health"]["fail_closed"] is True
    assert "candidate_producer_state_missing" in missing["health"]["reasons"]
    assert missing["forward_reopen_progress"]["gate_ready"] is False
    assert "observer_health_fail_closed" in missing["forward_reopen_progress"][
        "not_ready_reasons"
    ]
    assert not forward_ledger.exists()

    candidate_state = candidate_dir / "state.json"
    candidate_state.write_text(
        json.dumps(candidate_state_payload(candidate_ledger, "2026-07-27")),
        encoding="utf-8",
    )
    stale = refresh_form4_sale_overhang_forward_ledger(
        as_of="2026-07-28",
        candidate_ledger_path=candidate_ledger,
        candidate_state_path=candidate_state,
        data_dir=data_dir,
        ledger_path=forward_ledger,
    )
    assert stale["status"] == "stale"
    assert "candidate_producer_stale" in stale["health"]["reasons"]
    assert stale["decision_rows_written"] == 0

    candidate_state.write_text(
        json.dumps(candidate_state_payload(candidate_ledger, "2026-07-28")),
        encoding="utf-8",
    )
    summary_path = data_dir / "form4_sale_overhang_context_summary_20260728.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.pop("content_identity")
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    missing_identity = refresh_form4_sale_overhang_forward_ledger(
        as_of="2026-07-28",
        candidate_ledger_path=candidate_ledger,
        candidate_state_path=candidate_state,
        data_dir=data_dir,
        ledger_path=forward_ledger,
    )
    assert missing_identity["status"] == "unavailable"
    assert "current_form4_context_content_identity_missing" in missing_identity[
        "health"
    ]["reasons"]
    assert missing_identity["forward_reopen_progress"]["gate_ready"] is False
