import json

import quant.candidate_decision_training_ledger as ledger_module
from quant.candidate_decision_training_ledger import (
    FORM4_FORWARD_OBSERVER_KEY,
    RULE_VERSION,
    SURFACE_CONTRACT,
    append_candidate_decision_training_snapshot,
    build_candidate_decision_training_snapshot,
    settle_candidate_decision_training_outcomes,
)


def _candidate(ticker="AAA", *, rank=1, backtest_reason="selected_by_entry_plan"):
    backtest_decision = "buy" if backtest_reason == "selected_by_entry_plan" else "deferred"
    return {
        "rank": rank,
        "ticker": ticker,
        "strategy": "trend_long",
        "sector": "Technology",
        "entry_price": 100.0,
        "stop_price": 95.0,
        "target_price": 118.0,
        "risk_reward_ratio": 2.5,
        "trade_quality_score": 0.91,
        "confidence_score": 1.0,
        "days_to_earnings": 22,
        "shares_to_buy": 10,
        "position_value_usd": 1000.0,
        "live_accounting": {
            "decision": backtest_decision,
            "reason": backtest_reason,
            "available_slots": 3,
        },
        "backtest_accounting": {
            "decision": backtest_decision,
            "reason": backtest_reason,
            "available_slots": 3,
        },
    }


def _review(rows):
    return {
        "diagnostic_only": True,
        "orders_changed": False,
        "candidate_count": len(rows),
        "candidates": rows,
    }


def _bars(start=100.0):
    rows = []
    for index, day in enumerate(
        [
            "2026-07-06",
            "2026-07-07",
            "2026-07-08",
            "2026-07-09",
            "2026-07-10",
            "2026-07-13",
            "2026-07-14",
            "2026-07-15",
            "2026-07-16",
            "2026-07-17",
            "2026-07-20",
            "2026-07-21",
            "2026-07-22",
            "2026-07-23",
            "2026-07-24",
            "2026-07-27",
            "2026-07-28",
            "2026-07-29",
            "2026-07-30",
            "2026-07-31",
            "2026-08-03",
        ]
    ):
        price = start + index
        rows.append({"date": day, "open": price, "close": price + 0.5})
    return rows


def test_build_snapshot_uses_next_equity_session_and_candidate_status():
    snapshot = build_candidate_decision_training_snapshot(
        as_of="2026-07-02",
        entry_candidate_review=_review(
            [
                _candidate("AAA"),
                _candidate("BBB", rank=2, backtest_reason="slot_sliced"),
            ]
        ),
        metadata={"source": "test"},
    )

    assert snapshot["rule_version"] == RULE_VERSION
    assert snapshot["trade_enabled"] is False
    assert snapshot["candidate_count"] == 2
    assert snapshot["entry_date_present_count"] == 2
    assert {row["entry_date"] for row in snapshot["rows"]} == {"2026-07-06"}
    by_ticker = {row["ticker"]: row for row in snapshot["rows"]}
    assert by_ticker["AAA"]["candidate_status"] == "selected"
    assert by_ticker["BBB"]["candidate_status"] == "slot_sliced"
    assert by_ticker["AAA"]["target_price_applicability"] == "present_signal_contract"
    assert by_ticker["AAA"]["production_impact"]["orders_changed"] is False


def test_append_snapshot_is_duplicate_safe_and_writes_state(tmp_path):
    ledger = tmp_path / "rows.jsonl"
    snapshot = build_candidate_decision_training_snapshot(
        as_of="2026-07-02",
        entry_candidate_review=_review([_candidate("AAA"), _candidate("BBB", rank=2)]),
    )

    first = append_candidate_decision_training_snapshot(snapshot, ledger)
    second = append_candidate_decision_training_snapshot(snapshot, ledger)

    assert first["rows_written"] == 2
    assert second["rows_written"] == 0
    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert {row["record_type"] for row in records} == {"candidate_decision_snapshot"}
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["surface_contract"] == SURFACE_CONTRACT
    assert state["rows_skipped_duplicate"] == 2
    assert state["last_nonempty_as_of"] == "2026-07-02"
    assert state["ledger_content_identity"]["status"] == "ok"
    assert state["ledger_content_identity"]["record_count"] == 2
    assert len(state["ledger_content_identity"]["sha256"]) == 64


def test_settlement_appends_fixed_horizon_outcomes_once(tmp_path):
    ledger = tmp_path / "rows.jsonl"
    snapshot = build_candidate_decision_training_snapshot(
        as_of="2026-07-02",
        entry_candidate_review=_review([_candidate("AAA")]),
    )
    append_candidate_decision_training_snapshot(snapshot, ledger)

    first = settle_candidate_decision_training_outcomes(
        ledger_path=ledger,
        as_of="2026-08-03",
        ohlcv_by_ticker={
            "AAA": _bars(100.0),
            "SPY": _bars(400.0),
            "QQQ": _bars(500.0),
        },
    )
    second = settle_candidate_decision_training_outcomes(
        ledger_path=ledger,
        as_of="2026-08-03",
        ohlcv_by_ticker={
            "AAA": _bars(100.0),
            "SPY": _bars(400.0),
            "QQQ": _bars(500.0),
        },
    )

    assert first["outcome_rows_written"] == 2
    assert second["outcome_rows_written"] == 0
    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    outcomes = [row for row in records if row["record_type"] == "candidate_decision_outcome"]
    assert {row["horizon"] for row in outcomes} == {"10d", "20d"}
    assert all(row["oracle_label_used"] is False for row in outcomes)
    assert all(row["replacement_value_vs_spy_usd"] is not None for row in outcomes)


def test_settlement_wires_form4_forward_refresh_without_changing_outcomes(
    monkeypatch,
    tmp_path,
):
    ledger = tmp_path / "rows.jsonl"
    snapshot = build_candidate_decision_training_snapshot(
        as_of="2026-07-02",
        entry_candidate_review=_review([_candidate("AAA")]),
    )
    append_candidate_decision_training_snapshot(snapshot, ledger)
    calls = []

    def _fake_refresh(**kwargs):
        calls.append(kwargs)
        return {
            "status": "ok",
            "gate_ready": False,
            "trade_enabled": False,
        }

    monkeypatch.setattr(
        ledger_module,
        "_refresh_form4_sale_overhang_forward_observer",
        _fake_refresh,
    )
    result = settle_candidate_decision_training_outcomes(
        ledger_path=ledger,
        as_of="2026-08-03",
        ohlcv_by_ticker={
            "AAA": _bars(100.0),
            "SPY": _bars(400.0),
            "QQQ": _bars(500.0),
        },
        refresh_form4_forward=True,
        form4_forward_kwargs={"effective_date": "2026-07-28"},
    )

    assert result["outcome_rows_written"] == 2
    assert result[FORM4_FORWARD_OBSERVER_KEY]["status"] == "ok"
    assert len(calls) == 1
    assert calls[0]["as_of"] == "2026-08-03"
    assert calls[0]["candidate_ledger_path"] == ledger
    assert calls[0]["kwargs"]["effective_date"] == "2026-07-28"
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state[FORM4_FORWARD_OBSERVER_KEY]["gate_ready"] is False
    assert state["ledger_content_identity"]["record_count"] == 3
