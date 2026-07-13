import json

from quant.exit_lifecycle_outcomes import (
    OUTCOME_RULE_VERSION,
    persist_exit_lifecycle_outcome_ledger,
)


def _source_row(ticker="AAA", *, as_of="2026-07-02", event_type="no_advisory_event"):
    return {
        "rule_version": "exit_lifecycle_shadow_log_v1",
        "ticker": ticker,
        "as_of_date": as_of,
        "generated_at": "2026-07-02T23:00:00Z",
        "shares": 10,
        "avg_cost": 90.0,
        "market_value_usd": 1000.0,
        "unrealized_pnl_pct": 0.05,
        "daily_return_pct": 0.01,
        "breach_status": "OK",
        "trailing_stop_from_hwm": 95.0,
        "drawdown_from_hwm_pct": -0.03,
        "entry_date": "2026-06-01",
        "target_price": 120.0,
        "advisory_events": [{"event_type": event_type}],
        "has_advisory_event": event_type != "no_advisory_event",
        "read_only": True,
        "alters_orders": False,
        "trade_enabled": False,
    }


def _bars(start=100.0, days=None):
    dates = days or [
        "2026-07-02",
        "2026-07-06",
        "2026-07-07",
        "2026-07-08",
        "2026-07-09",
        "2026-07-10",
        "2026-07-13",
    ]
    rows = []
    for index, day in enumerate(dates):
        price = start + index
        rows.append({"date": day, "open": price, "close": price + 0.5})
    return rows


def _write_source(data_root, rows, tag="20260702"):
    source = data_root / "exit_lifecycle"
    source.mkdir(parents=True)
    path = source / f"exit_lifecycle_{tag}.jsonl"
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def test_persist_exit_lifecycle_outcomes_writes_closed_rows(tmp_path):
    data_root = tmp_path / "data"
    _write_source(
        data_root,
        [
            _source_row("AAA", event_type="hard_stop_breach"),
            _source_row("BBB"),
        ],
    )

    summary = persist_exit_lifecycle_outcome_ledger(
        today="2026-07-13",
        data_dir=data_root,
        ohlcv_by_ticker={
            "AAA": _bars(100.0),
            "BBB": _bars(50.0),
            "SPY": _bars(400.0),
            "QQQ": _bars(500.0),
        },
    )

    assert summary["outcome_rule_version"] == OUTCOME_RULE_VERSION
    assert summary["candidate_outcome_rows"] == 2
    assert summary["settled_count"] == 2
    assert summary["production_impact"]["alters_exits"] is False
    assert summary["production_impact"]["alters_orders"] is False

    ledger = data_root / "exit_lifecycle" / "outcome_ledgers" / "exit_lifecycle_outcomes_20260713.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["AAA"]["advisory_bucket"] == "hard_stop"
    assert by_ticker["AAA"]["position_entry_date"] == "2026-06-01"
    assert by_ticker["AAA"]["target_price"] == 120.0
    assert by_ticker["AAA"]["target_price_scope"] == "position_contract_not_fixed_horizon_exit"
    assert by_ticker["AAA"]["h5_status"] == "closed"
    assert by_ticker["AAA"]["h5_replacement_value_vs_spy_usd"] is not None
    assert by_ticker["AAA"]["trade_enabled"] is False


def test_exit_lifecycle_outcomes_keep_unsettled_rows_pending(tmp_path):
    data_root = tmp_path / "data"
    _write_source(data_root, [_source_row("AAA", as_of="2026-07-09")], tag="20260709")

    summary = persist_exit_lifecycle_outcome_ledger(
        today="2026-07-09",
        data_dir=data_root,
        ohlcv_by_ticker={
            "AAA": _bars(100.0, days=["2026-07-09", "2026-07-10"]),
            "SPY": _bars(400.0, days=["2026-07-09", "2026-07-10"]),
            "QQQ": _bars(500.0, days=["2026-07-09", "2026-07-10"]),
        },
    )

    assert summary["candidate_outcome_rows"] == 1
    assert summary["settled_count"] == 0
    assert summary["unsettled_count"] == 1
    ledger = data_root / "exit_lifecycle" / "outcome_ledgers" / "exit_lifecycle_outcomes_20260709.jsonl"
    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    assert row["outcome_status"] == "pending_forward_close"
    assert row["h5_status"] == "unsettled_horizon"
