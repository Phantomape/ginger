"""Tests for the live-vs-model drift reconciliation surface (exp-20260706-019)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from fill_model import SLIPPAGE_BPS_ENTRY, apply_slippage  # noqa: E402
import live_drift_reconciliation as ldr  # noqa: E402
from live_drift_reconciliation import (  # noqa: E402
    ALERT_CONSECUTIVE_SESSIONS,
    build_live_drift_reconciliation,
    evaluate_drift_alert,
    reconcile_position,
    strategy_bucket,
)


def _bars():
    return [
        {"date": "2026-05-29", "open": 99.0, "close": 99.5},
        {"date": "2026-06-01", "open": 100.0, "close": 101.0},
        {"date": "2026-06-02", "open": 101.0, "close": 102.0},
        {"date": "2026-06-03", "open": 102.0, "close": 104.0},
    ]


def _position(**overrides):
    base = {
        "ticker": "NVDA",
        "direction": "long",
        "shares": 10.0,
        "avg_cost": 100.30,
        "entry_date": "2026-06-01",
        "market_val": 1040.0,
        "unrealized_pl": 37.0,
        "opened_by_strategy": "trend_long",
        "sleeve": "core",
        "position_id": 111,
    }
    base.update(overrides)
    return base


def _order_snapshot(
    *,
    ticker: str = "NVDA",
    quantity: float = 10.0,
    session: str = "RTH",
    fill_outside_rth: bool = False,
    create_date: str = "2026-06-01",
    order_id: str = "entry-1",
):
    return {
        "record_type": "broker_order_snapshot",
        "ledger_sequence": 1,
        "fact": {
            "order_id": order_id,
            "ticker": ticker,
            "trd_side": "BUY",
            "create_time": f"{create_date} 09:30:01.000",
            "dealt_qty": str(quantity),
            "dealt_avg_price": "100.30",
            "order_status": "FILLED_ALL",
            "session": session,
            "fill_outside_rth": fill_outside_rth,
        },
    }


def _signal_payload(
    *,
    ticker: str = "NVDA",
    strategy: str = "trend_long",
    shares_to_buy: float = 10.0,
    next_session: bool = True,
):
    return {
        "signals": [
            {
                "ticker": ticker,
                "strategy": strategy,
                "entry_note": (
                    "Execute next-day open; cancel outside entry envelope"
                    if next_session
                    else "operator decides timing"
                ),
                "sizing": {"shares_to_buy": shares_to_buy},
                "target_price": 120.0,
            }
        ]
    }


def _valid_evidence(*, ticker: str = "NVDA", strategy: str = "trend_long"):
    return {
        "order_snapshots": [_order_snapshot(ticker=ticker)],
        "quant_signals_fn": lambda decision_date: (
            _signal_payload(ticker=ticker, strategy=strategy)
            if decision_date == "2026-05-29"
            else None
        ),
    }


def _eligible_alert_row(asof: str, *, position_id: int, drift: float, fill: float):
    return {
        "asof_date": asof,
        "market_session_date": asof,
        "position_id": position_id,
        "strategy_bucket": "core",
        "reconcilable": True,
        "market_val": 10_000.0,
        "trajectory_drift_pct": drift,
        "fill_drift_pct": fill,
        "rule_version": "live_drift_reconciliation_v4",
        "alert_eligibility_contract": "live_drift_reconciliation_v4",
        "core_execution_alert_eligible": True,
        "broker_entry_evidence_status": "verified_regular_session_fill",
        "policy_decision_evidence_status": "verified_prior_next_session_top_level_signal",
    }


def _write_warehouse(path: Path, rows: list[tuple[str, str, float, float]]) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("create table ohlcv (ticker text, date text, open real, close real)")
        con.executemany("insert into ohlcv values (?, ?, ?, ?)", rows)
        con.commit()
    finally:
        con.close()


def test_strategy_bucket_classification():
    assert strategy_bucket(_position()) == "core"
    assert strategy_bucket(
        _position(
            opened_by_strategy="fomo",
            sleeve="core_strategy",
            slot_policy="consumes_core_slot",
        )
    ) == "core"
    assert strategy_bucket(
        _position(sleeve="core", slot_policy="no_core_slot")
    ) == "sleeve"
    assert strategy_bucket(_position(opened_by_strategy="legacy", sleeve="discretionary")) == (
        "discretionary_legacy"
    )
    assert strategy_bucket(_position(sleeve="form4", opened_by_strategy="form4_sleeve")) == "sleeve"


def test_core_execution_alert_eligibility_requires_core_exposure_and_policy_provenance():
    policy_core = reconcile_position(
        _position(), _bars(), "2026-06-03", **_valid_evidence()
    )
    policy_non_core = reconcile_position(
        _position(sleeve="paper", slot_policy="no_core_slot"),
        _bars(),
        "2026-06-03",
    )
    fomo_core = reconcile_position(
        _position(
            opened_by_strategy="fomo",
            sleeve="core_strategy",
            slot_policy="consumes_core_slot",
        ),
        _bars(),
        "2026-06-03",
    )

    assert policy_core["core_execution_alert_eligible"] is True
    assert policy_core["core_execution_alert_exclusion_reason"] is None
    assert policy_core["broker_entry_evidence_status"] == "verified_regular_session_fill"
    assert policy_core["policy_decision_evidence_status"] == (
        "verified_prior_next_session_top_level_signal"
    )
    assert policy_non_core["core_execution_alert_eligible"] is False
    assert policy_non_core["core_execution_alert_exclusion_reason"] == "non_core_exposure"
    assert fomo_core["core_execution_alert_eligible"] is False
    assert fomo_core["core_execution_alert_exclusion_reason"] == (
        "entry_not_attributable_to_core_policy"
    )


def test_default_warehouse_paths_prefer_hot_current_surface():
    assert ldr.WAREHOUSE_PATHS[0].name == "warehouse_main_hot.sqlite"


def test_bars_from_warehouse_prefers_hot_and_falls_back_on_empty(tmp_path, monkeypatch):
    hot = tmp_path / "warehouse_main_hot.sqlite"
    stale = tmp_path / "warehouse_main.sqlite"
    _write_warehouse(stale, [("HOOD", "2026-06-12", 100.0, 101.0)])
    _write_warehouse(hot, [("HOOD", "2026-06-18", 107.0, 108.0)])

    monkeypatch.setattr(ldr, "WAREHOUSE_PATHS", (hot, stale))
    rows = ldr._bars_from_warehouse("HOOD")
    assert rows[-1]["date"] == "2026-06-18"

    empty_hot = tmp_path / "empty_hot.sqlite"
    _write_warehouse(empty_hot, [])
    monkeypatch.setattr(ldr, "WAREHOUSE_PATHS", (empty_hot, stale))
    rows = ldr._bars_from_warehouse("HOOD")
    assert rows[-1]["date"] == "2026-06-12"


def test_reconcile_position_arithmetic():
    row = reconcile_position(_position(), _bars(), "2026-06-03")
    assert row["reconcilable"] is True

    modeled_entry = apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    assert abs(row["modeled_entry_price"] - round(modeled_entry, 4)) < 1e-9
    assert abs(row["fill_drift_pct"] - (100.30 / modeled_entry - 1.0)) < 1e-6
    # realized mark = 1040/10 = 104.0 vs avg_cost 100.30
    assert abs(row["realized_return_pct"] - (104.0 / 100.30 - 1.0)) < 1e-6
    assert abs(row["modeled_return_pct"] - (104.0 / modeled_entry - 1.0)) < 1e-6
    assert abs(
        row["trajectory_drift_pct"]
        - (row["realized_return_pct"] - row["modeled_return_pct"])
    ) < 1e-6


def test_reconcile_position_entry_on_non_session_uses_next_bar():
    row = reconcile_position(_position(entry_date="2026-05-31"), _bars(), "2026-06-03")
    assert row["reconcilable"] is True
    assert abs(
        row["modeled_entry_price"] - round(apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy"), 4)
    ) < 1e-9


def test_reconcile_position_fail_safe_reasons():
    assert reconcile_position(_position(entry_date=None), _bars(), "2026-06-03")["reason"] == (
        "missing_entry_date"
    )
    assert reconcile_position(_position(avg_cost=None), _bars(), "2026-06-03")["reason"] == (
        "missing_cost_basis"
    )
    assert reconcile_position(_position(entry_date="2026-07-01"), _bars(), "2026-06-03")[
        "reason"
    ] == "missing_entry_bar"
    assert reconcile_position(_position(direction="short"), _bars(), "2026-06-03")["reason"] == (
        "non_long_direction_v2"
    )


def test_build_persists_idempotent_ledger_and_state(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    state_path = tmp_path / "state.json"
    kwargs = dict(
        as_of="2026-06-03",
        positions=[_position(), _position(ticker="AMD", position_id=222, sleeve="discretionary", opened_by_strategy="legacy")],
        bars_fn=lambda ticker: _bars(),
        ledger_path=ledger,
        state_path=state_path,
    )
    state1 = build_live_drift_reconciliation(**kwargs)
    state2 = build_live_drift_reconciliation(**kwargs)  # same-day rerun

    assert state1["appended_rows"] == 2
    assert state2["appended_rows"] == 0  # idempotent per (asof, position_id)
    rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2
    assert state1["reconciled_count"] == 2
    assert "core" in state1["buckets"] and "discretionary_legacy" in state1["buckets"]
    assert state1["production_impact"] == "observe_only_no_orders_no_ranking_no_sizing"
    assert json.loads(state_path.read_text(encoding="utf-8"))["rule_version"] == (
        "live_drift_reconciliation_v4"
    )


def test_positions_file_uses_all_shared_account_groups(tmp_path):
    positions_path = tmp_path / "positions.json"
    positions_path.write_text(
        json.dumps(
            {
                "positions": [
                    _position(
                        ticker="AMD",
                        position_id=101,
                        sleeve="paper",
                        slot_policy="no_core_slot",
                    )
                ],
                "core_positions": [
                    _position(
                        ticker="MRVL",
                        position_id=102,
                        opened_by_strategy="fomo",
                        sleeve="core_strategy",
                        slot_policy="consumes_core_slot",
                    )
                ],
                "observations": [
                    _position(
                        ticker="WAT",
                        position_id=103,
                        sleeve="observation",
                        slot_policy="no_core_slot",
                    )
                ],
            }
        ),
        encoding="utf-8",
    )

    state = build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions_path=positions_path,
        bars_fn=lambda ticker: _bars(),
        ledger_path=tmp_path / "ledger.jsonl",
        state_path=tmp_path / "state.json",
        persist=False,
    )

    assert state["position_count"] == 3
    assert state["buckets"]["core"]["positions"] == 1
    assert state["buckets"]["sleeve"]["positions"] == 2


def test_drift_alert_requires_consecutive_breaches():
    def _rows(asof, drift):
        day = int(asof[-2:])
        return [_eligible_alert_row(asof, position_id=day, drift=drift, fill=0.0)]

    breach_days = [f"2026-06-{d:02d}" for d in range(1, ALERT_CONSECUTIVE_SESSIONS + 1)]
    ledger = []
    for day in breach_days:
        ledger.extend(_rows(day, -0.02))
    alert = evaluate_drift_alert(ledger)
    assert alert["consecutive_breach_sessions"] == ALERT_CONSECUTIVE_SESSIONS
    assert alert["trajectory_alert"] is True

    # one healthy session in the middle resets the streak
    ledger2 = []
    for i, day in enumerate(breach_days):
        ledger2.extend(_rows(day, -0.02 if i != 5 else 0.0))
    alert2 = evaluate_drift_alert(ledger2)
    assert alert2["trajectory_alert"] is False


def test_fomo_core_position_keeps_raw_five_pct_drift_but_cannot_alert(tmp_path):
    modeled_entry = apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    fomo = _position(
        ticker="MRVL",
        position_id=5438192453869111284,
        avg_cost=modeled_entry * 1.05,
        opened_by_strategy="fomo",
        sleeve="core_strategy",
        slot_policy="consumes_core_slot",
    )
    ledger = tmp_path / "ledger.jsonl"
    state = build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions=[fomo],
        bars_fn=lambda ticker: _bars(),
        ledger_path=ledger,
        state_path=tmp_path / "state.json",
    )

    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["strategy_bucket"] == "core"
    assert row["fill_drift_pct"] == 0.05
    assert row["entry_strategy_provenance"] == "fomo"
    assert row["entry_strategy_provenance_field"] == "opened_by_strategy"
    assert row["core_execution_alert_eligible"] is False
    assert row["core_execution_alert_exclusion_reason"] == (
        "entry_not_attributable_to_core_policy"
    )
    assert state["buckets"]["core"]["mean_fill_drift_pct"] == 0.05
    assert state["alert"]["fill_alert"] is False
    assert state["alert"]["latest_mean_fill_drift_pct"] is None


def test_bars_unavailable_row_keeps_fail_closed_alert_provenance(tmp_path):
    ledger = tmp_path / "ledger.jsonl"

    def unavailable(ticker):
        raise RuntimeError("warehouse offline")

    build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions=[
            _position(
                ticker="MRVL",
                position_id=717,
                opened_by_strategy="fomo",
                sleeve="core_strategy",
                slot_policy="consumes_core_slot",
            )
        ],
        bars_fn=unavailable,
        ledger_path=ledger,
        state_path=tmp_path / "state.json",
    )

    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["reconcilable"] is False
    assert row["reason"] == "bars_unavailable: warehouse offline"
    assert row["entry_strategy_provenance"] == "fomo"
    assert row["core_execution_alert_eligible"] is False
    assert row["core_execution_alert_exclusion_reason"] == (
        "entry_not_attributable_to_core_policy"
    )


def test_policy_core_trend_and_breakout_fills_remain_alert_eligible():
    modeled_entry = apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    for strategy in ("trend_long", "breakout_long"):
        row = reconcile_position(
            _position(avg_cost=modeled_entry * 1.01, opened_by_strategy=strategy),
            _bars(),
            "2026-06-03",
            **_valid_evidence(strategy=strategy),
        )
        assert row["strategy_bucket"] == "core"
        assert row["entry_strategy_provenance"] == strategy
        assert row["core_execution_alert_eligible"] is True
        assert row["core_execution_alert_exclusion_reason"] is None
        alert = evaluate_drift_alert([row])
        assert alert["fill_alert"] is True
        assert alert["latest_mean_fill_drift_pct"] == 0.01


def test_latest_ineligible_core_session_resets_alerts():
    rows = [
        _eligible_alert_row(
            f"2026-06-{day:02d}", position_id=day, drift=-0.02, fill=0.01
        )
        for day in range(1, ALERT_CONSECUTIVE_SESSIONS + 1)
    ]
    rows.append(
        {
            "asof_date": "2026-06-11",
            "market_session_date": "2026-06-11",
            "position_id": 11,
            "strategy_bucket": "core",
            "reconcilable": True,
            "market_val": 10_000.0,
            "trajectory_drift_pct": -0.02,
            "fill_drift_pct": 0.05,
            "rule_version": "live_drift_reconciliation_v4",
            "alert_eligibility_contract": "live_drift_reconciliation_v4",
            "core_execution_alert_eligible": False,
            "broker_entry_evidence_status": "outside_regular_session_fill",
            "policy_decision_evidence_status": (
                "verified_prior_next_session_top_level_signal"
            ),
        }
    )

    alert = evaluate_drift_alert(rows)
    assert alert["sessions_observed"] == ALERT_CONSECUTIVE_SESSIONS + 1
    assert alert["consecutive_breach_sessions"] == 0
    assert alert["trajectory_alert"] is False
    assert alert["fill_alert"] is False
    assert alert["latest_mean_fill_drift_pct"] is None


def test_missing_v4_evidence_fails_closed_for_every_ledger_version():
    row = {
        "asof_date": "2026-06-03",
        "strategy_bucket": "core",
        "reconcilable": True,
        "market_val": 10_000.0,
        "trajectory_drift_pct": -0.02,
        "fill_drift_pct": 0.01,
    }
    for version in (
        "live_drift_reconciliation_v1",
        "live_drift_reconciliation_v2",
        "live_drift_reconciliation_v3",
        "live_drift_reconciliation_v4",
    ):
        assert evaluate_drift_alert([{**row, "rule_version": version}])["fill_alert"] is False


def test_matching_current_position_enriches_v2_history_only_in_memory(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    legacy_row = {
        "asof_date": "2026-06-01",
        "position_id": 919,
        "ticker": "MRVL",
        "strategy_bucket": "core",
        "reconcilable": True,
        "market_val": 10_000.0,
        "trajectory_drift_pct": -0.02,
        "fill_drift_pct": 0.05,
        "rule_version": "live_drift_reconciliation_v2",
    }
    original_bytes = (json.dumps(legacy_row, sort_keys=True) + "\n").encode()
    ledger.write_bytes(original_bytes)
    fomo = _position(
        ticker="MRVL",
        position_id=919,
        opened_by_strategy="fomo",
        sleeve="core_strategy",
        slot_policy="consumes_core_slot",
    )

    state = build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions=[fomo],
        bars_fn=lambda ticker: [],
        persist=False,
        ledger_path=ledger,
        state_path=tmp_path / "state.json",
    )

    assert state["alert"]["sessions_observed"] == 1
    assert state["alert"]["fill_alert"] is False
    assert state["alert"]["latest_mean_fill_drift_pct"] is None
    assert ledger.read_bytes() == original_bytes
    assert "core_execution_alert_eligible" not in json.loads(ledger.read_text())


def test_same_day_fresh_row_overrides_history_for_alert_without_rewrite(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    historical_row = {
        "asof_date": "2026-06-03",
        "position_id": 818,
        "ticker": "NVDA",
        "strategy_bucket": "core",
        "reconcilable": True,
        "market_val": 10_000.0,
        "trajectory_drift_pct": -0.02,
        "fill_drift_pct": 0.05,
        "rule_version": "live_drift_reconciliation_v2",
    }
    original_bytes = (json.dumps(historical_row, sort_keys=True) + "\n").encode()
    ledger.write_bytes(original_bytes)
    modeled_entry = apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    current = _position(position_id=818, avg_cost=modeled_entry * 1.001)

    state = build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions=[current],
        bars_fn=lambda ticker: _bars(),
        **_valid_evidence(),
        ledger_path=ledger,
        state_path=tmp_path / "state.json",
    )

    assert state["appended_rows"] == 0
    assert state["alert"]["fill_alert"] is False
    assert state["alert"]["latest_mean_fill_drift_pct"] == 0.001
    assert ledger.read_bytes() == original_bytes


def test_real_amzn_eth_shape_keeps_raw_2352bp_drift_but_is_ineligible():
    modeled_entry = apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    amzn = _position(
        ticker="AMZN",
        position_id=5438192453869111336,
        shares=3.0,
        avg_cost=modeled_entry * 1.02352,
        opened_by_strategy="breakout_long",
    )
    orders = [
        _order_snapshot(
            ticker="AMZN",
            quantity=1,
            session="ETH",
            fill_outside_rth=True,
            order_id="FS1CE949C89FBA1000",
        ),
        {
            **_order_snapshot(
                ticker="AMZN",
                quantity=2,
                session="ETH",
                fill_outside_rth=True,
                order_id="FS1CE94AA4E9FA1000",
            ),
            "ledger_sequence": 2,
        },
    ]
    row = reconcile_position(
        amzn,
        _bars(),
        "2026-06-03",
        order_snapshots=orders,
        quant_signals_fn=lambda decision_date: _signal_payload(
            ticker="AMZN", strategy="breakout_long", shares_to_buy=3
        ),
    )

    assert row["fill_drift_pct"] == 0.02352
    assert row["broker_entry_filled_qty"] == 3.0
    assert row["broker_entry_sessions"] == ["ETH"]
    assert row["broker_entry_evidence_status"] == "outside_regular_session_fill"
    assert row["core_execution_alert_eligible"] is False
    assert row["core_execution_alert_exclusion_reason"] == "outside_regular_session_fill"
    assert evaluate_drift_alert([row])["fill_alert"] is False


def test_verified_rth_or_all_fill_and_prior_final_signal_are_eligible():
    modeled_entry = apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    for session in ("RTH", "ALL"):
        row = reconcile_position(
            _position(avg_cost=modeled_entry * 1.01),
            _bars(),
            "2026-06-03",
            order_snapshots=[_order_snapshot(session=session, fill_outside_rth=False)],
            quant_signals_fn=lambda decision_date: _signal_payload(),
        )
        assert row["core_execution_alert_eligible"] is True
        assert row["broker_entry_evidence_status"] == "verified_regular_session_fill"
        assert row["policy_decision_date"] == "2026-05-29"
        assert row["policy_decision_evidence_status"] == (
            "verified_prior_next_session_top_level_signal"
        )


def test_missing_or_malformed_execution_evidence_fails_closed():
    missing_order = reconcile_position(
        _position(),
        _bars(),
        "2026-06-03",
        order_snapshots=[],
        quant_signals_fn=lambda decision_date: _signal_payload(),
    )
    malformed_order = reconcile_position(
        _position(),
        _bars(),
        "2026-06-03",
        order_snapshots=[{"not": "canonical"}],
        quant_signals_fn=lambda decision_date: _signal_payload(),
    )
    malformed_signal = reconcile_position(
        _position(),
        _bars(),
        "2026-06-03",
        order_snapshots=[_order_snapshot()],
        quant_signals_fn=lambda decision_date: {"signals": {}},
    )
    empty_signal = reconcile_position(
        _position(),
        _bars(),
        "2026-06-03",
        order_snapshots=[_order_snapshot()],
        quant_signals_fn=lambda decision_date: {"signals": []},
    )

    assert missing_order["core_execution_alert_exclusion_reason"] == (
        "matching_entry_buy_fill_missing"
    )
    assert malformed_order["core_execution_alert_exclusion_reason"] == (
        "broker_order_snapshots_malformed"
    )
    assert malformed_signal["core_execution_alert_exclusion_reason"] == (
        "policy_decision_snapshot_malformed"
    )
    assert empty_signal["core_execution_alert_exclusion_reason"] == (
        "matching_top_level_signal_missing"
    )
    assert not any(
        row["core_execution_alert_eligible"]
        for row in (missing_order, malformed_order, malformed_signal, empty_signal)
    )


def test_non_session_reruns_use_completed_market_session_for_append_and_streak(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    state_path = tmp_path / "state.json"
    kwargs = {
        "positions": [_position()],
        "bars_fn": lambda ticker: _bars(),
        "ledger_path": ledger,
        "state_path": state_path,
        **_valid_evidence(),
    }
    friday = build_live_drift_reconciliation(as_of="2026-06-05", **kwargs)
    saturday_utc = build_live_drift_reconciliation(
        as_of="2026-06-06T00:05:00+00:00", **kwargs
    )
    restarted = build_live_drift_reconciliation(as_of="2026-06-06", **kwargs)

    persisted = [json.loads(line) for line in ledger.read_text().splitlines() if line]
    assert friday["market_session_date"] == "2026-06-03"
    assert saturday_utc["market_session_date"] == "2026-06-03"
    assert saturday_utc["appended_rows"] == 0
    assert restarted["appended_rows"] == 0
    assert saturday_utc["alert"]["sessions_observed"] == 1
    assert restarted["alert"]["sessions_observed"] == 1
    assert len(persisted) == 1
    assert persisted[0]["market_session_date"] == "2026-06-03"


def test_v3_friday_and_saturday_rows_collapse_to_current_v4_market_session(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    legacy_rows = [
        {
            "asof_date": asof,
            "position_id": 111,
            "ticker": "NVDA",
            "strategy_bucket": "core",
            "reconcilable": True,
            "market_val": 1040.0,
            "trajectory_drift_pct": -0.02,
            "fill_drift_pct": 0.01,
            "rule_version": "live_drift_reconciliation_v3",
            "core_execution_alert_eligible": True,
        }
        for asof in ("2026-07-31", "2026-08-01")
    ]
    ledger.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in legacy_rows),
        encoding="utf-8",
    )
    bars = [
        {"date": "2026-07-30", "open": 99.0, "close": 99.5},
        {"date": "2026-07-31", "open": 100.0, "close": 104.0},
    ]
    position = _position(entry_date="2026-07-31")
    state = build_live_drift_reconciliation(
        as_of="2026-08-01",
        positions=[position],
        bars_fn=lambda ticker: bars,
        order_snapshots=[_order_snapshot(create_date="2026-07-31")],
        quant_signals_fn=lambda decision_date: (
            _signal_payload() if decision_date == "2026-07-30" else None
        ),
        ledger_path=ledger,
        state_path=tmp_path / "state.json",
    )

    assert state["market_session_date"] == "2026-07-31"
    assert state["appended_rows"] == 0
    assert state["alert"]["sessions_observed"] == 1


def test_next_completed_session_advances_once_not_by_wall_clock(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    base_bars = _bars()
    evidence = _valid_evidence()
    first = build_live_drift_reconciliation(
        as_of="2026-06-05",
        positions=[_position()],
        bars_fn=lambda ticker: base_bars,
        ledger_path=ledger,
        state_path=tmp_path / "state.json",
        **evidence,
    )
    next_bars = base_bars + [{"date": "2026-06-08", "open": 105.0, "close": 106.0}]
    second = build_live_drift_reconciliation(
        as_of="2026-06-08",
        positions=[_position()],
        bars_fn=lambda ticker: next_bars,
        ledger_path=ledger,
        state_path=tmp_path / "state.json",
        **evidence,
    )
    same_session = build_live_drift_reconciliation(
        as_of="2026-06-09T01:00:00+00:00",
        positions=[_position()],
        bars_fn=lambda ticker: next_bars,
        ledger_path=ledger,
        state_path=tmp_path / "state.json",
        **evidence,
    )

    assert first["appended_rows"] == 1
    assert second["appended_rows"] == 1
    assert second["alert"]["sessions_observed"] == 2
    assert same_session["appended_rows"] == 0
    assert same_session["alert"]["sessions_observed"] == 2


def test_empty_book_is_deterministic_and_does_not_alert(tmp_path):
    kwargs = dict(
        as_of="2026-06-06",
        positions=[],
        order_snapshots=[],
        quant_signals_fn=lambda decision_date: None,
        ledger_path=tmp_path / "ledger.jsonl",
        state_path=tmp_path / "state.json",
        persist=False,
    )
    first = build_live_drift_reconciliation(**kwargs)
    second = build_live_drift_reconciliation(**kwargs)
    for state in (first, second):
        assert state["position_count"] == 0
        assert state["market_session_date"] is None
        assert state["alert"]["sessions_observed"] == 0
        assert state["alert"]["fill_alert"] is False


def test_suspect_multi_fill_excluded_from_bucket_stats(tmp_path):
    # avg_cost 130 vs first-session modeled entry ~100 => +30% fake fill drift
    scaled_in = _position(avg_cost=130.0, market_val=1040.0, position_id=333)
    state = build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions=[_position(), scaled_in],
        bars_fn=lambda ticker: _bars(),
        ledger_path=tmp_path / "ledger.jsonl",
        state_path=tmp_path / "state.json",
    )
    core = state["buckets"]["core"]
    assert core["reconciled"] == 2
    assert core["suspect_multi_fill"] == 1
    # aggregates come from the clean row only
    assert core["notional_usd"] == 1040.0


def test_positions_file_missing_is_fail_safe(tmp_path):
    state = build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions_path=tmp_path / "nope.json",
        ledger_path=tmp_path / "ledger.jsonl",
        state_path=tmp_path / "state.json",
        persist=False,
    )
    assert state["status"] == "positions_unavailable"
