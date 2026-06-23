import json

from quant.core_risk_intensity_ledger import (
    RULE_VERSION,
    append_core_risk_intensity_observation_snapshot,
    build_core_risk_intensity_observation_snapshot,
)


def _signal(ticker, risk_pct, *, base=0.01, strategy="trend_long", shares=10):
    return {
        "ticker": ticker,
        "strategy": strategy,
        "sector": "Technology",
        "entry_price": 100.0,
        "stop_price": 95.0,
        "target_price": 115.0,
        "sizing": {
            "base_risk_pct": base,
            "risk_pct": risk_pct,
            "shares_to_buy": shares,
            "position_value_usd": shares * 100.0,
            "risk_amount_usd": shares * 5.0,
            "risk_on_unmodified_risk_multiplier_applied": risk_pct / base,
            "tqs_risk_multiplier_applied": 1.0,
        },
    }


def test_build_snapshot_computes_risk_intensity_and_statuses():
    selected = _signal("AAA", 0.02)
    sliced = _signal("BBB", 0.005, strategy="breakout_long")
    deferred = _signal("CCC", 0.015)
    missing = {"ticker": "DDD", "strategy": "trend_long", "sizing": {}}

    snapshot = build_core_risk_intensity_observation_snapshot(
        as_of="2026-06-22",
        advisory_signals=[selected, sliced, deferred, missing],
        selected_signals=[selected],
        entry_execution_plan={
            "slot_sliced_signals": [sliced],
            "deferred_breakout_signals": [deferred],
        },
        metadata={"source": "test"},
    )

    assert snapshot["rule_version"] == RULE_VERSION
    assert snapshot["trade_enabled"] is False
    assert snapshot["candidate_count"] == 3
    assert snapshot["selected_count"] == 1
    assert snapshot["skipped_count"] == 1
    assert snapshot["skip_reasons"] == {"missing_or_nonpositive_base_risk_pct": 1}

    by_ticker = {row["ticker"]: row for row in snapshot["rows"]}
    assert by_ticker["AAA"]["candidate_status"] == "selected"
    assert by_ticker["BBB"]["candidate_status"] == "slot_sliced"
    assert by_ticker["CCC"]["candidate_status"] == "deferred_breakout"
    assert by_ticker["AAA"]["risk_intensity"] == 2.0
    assert by_ticker["BBB"]["risk_intensity"] == 0.5
    assert by_ticker["AAA"]["risk_multiplier_keys"] == [
        "risk_on_unmodified_risk_multiplier_applied"
    ]
    assert by_ticker["AAA"]["risk_intensity_daily_bucket"] == "high"
    assert by_ticker["BBB"]["risk_intensity_daily_bucket"] == "low"


def test_append_snapshot_is_idempotent(tmp_path):
    snapshot = build_core_risk_intensity_observation_snapshot(
        as_of="2026-06-22",
        advisory_signals=[_signal("AAA", 0.02), _signal("BBB", 0.01)],
        selected_signals=[],
    )
    ledger = tmp_path / "snapshots.jsonl"

    first = append_core_risk_intensity_observation_snapshot(snapshot, ledger)
    second = append_core_risk_intensity_observation_snapshot(snapshot, ledger)

    assert first["rows_written"] == 2
    assert second["rows_written"] == 0
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["ticker"] for row in rows} == {"AAA", "BBB"}
