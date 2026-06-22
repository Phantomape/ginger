"""Focused tests for forward replacement-value enrichment (exp-20260611-020)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import forward_replacement_value as frv


BARS = {
    "SPY": {
        "2026-05-05": {"open": 100.0, "close": 101.0},
        "2026-05-08": {"open": 103.0, "close": 103.5},
        "2026-05-15": {"open": 102.0, "close": 104.0},
    },
    "QQQ": {
        "2026-05-05": {"open": 200.0, "close": 201.0},
        "2026-05-08": {"open": 204.0, "close": 205.0},
        "2026-05-15": {"open": 208.0, "close": 210.0},
    },
}


def _row(**overrides):
    row = {
        "ticker": "GS",
        "decision_id": "TEST:row:2026-05-05:GS",
        "entry_date": "2026-05-05",
        "exit_date": "2026-05-15",
        "pnl": 390.84,
        "net_return_pct": 3.908409,
        "entry_price": 909.73,
        "exit_price": 948.47,
    }
    row.update(overrides)
    return row


def test_notional_explicit_wins():
    notional, method = frv._notional_for_row(_row(notional_usd=70000.0))
    assert notional == 70000.0
    assert method == "explicit"


def test_notional_derived_percent_units():
    notional, method = frv._notional_for_row(_row())
    assert method == "derived_from_net_return_percent"
    assert abs(notional - 10000.0) < 1.0


def test_notional_derived_fraction_units():
    # low_deployment-style fraction net_return with no prices
    row = {"pnl": 487.29, "net_return_pct": 0.006961}
    notional, method = frv._notional_for_row(row)
    assert method == "derived_from_net_return_fraction"
    assert abs(notional - 70000.0) < 100.0


def test_notional_missing():
    notional, method = frv._notional_for_row({"pnl": 0.0})
    assert notional is None
    assert method == "missing"


def test_enrich_row_fields_and_idempotency():
    state = {"closed_positions": [_row()]}
    records = frv.enrich_state_closed_rows(state, BARS, "2026-06-11", "test_sleeve")
    assert len(records) == 1
    row = state["closed_positions"][0]
    assert row["replacement_value_rule_version"] == frv.RULE_VERSION
    assert row["replacement_value_status"] == "enriched"
    assert row["replacement_value_vs_cash_usd"] == 390.84

    notional = row["replacement_value_notional_usd"]
    spy = frv._comparator_pnl(BARS["SPY"], "2026-05-05", "2026-05-15", notional)
    qqq = frv._comparator_pnl(BARS["QQQ"], "2026-05-05", "2026-05-15", notional)
    assert row["replacement_value_vs_spy_usd"] == round(390.84 - spy["net_pnl_usd"], 2)
    assert row["replacement_value_vs_qqq_usd"] == round(390.84 - qqq["net_pnl_usd"], 2)

    # comparator math: slippage on both legs plus round-trip cost
    entry_fill = 100.0 * (1 + frv.SLIPPAGE_BPS_ENTRY / 10000.0)
    exit_fill = 104.0 * (1 - frv.SLIPPAGE_BPS_TARGET / 10000.0)
    expected = notional * (exit_fill / entry_fill - 1.0) - notional * frv.ROUND_TRIP_COST_PCT
    assert abs(spy["net_pnl_usd"] - expected) < 0.02

    # second pass must be a no-op
    assert frv.enrich_state_closed_rows(state, BARS, "2026-06-12", "test_sleeve") == []
    assert row["replacement_value_asof"] == "2026-06-11"


def test_enrich_row_refreshes_missing_comparator_bars():
    stale = _row(
        replacement_value_rule_version=frv.RULE_VERSION,
        replacement_value_status="missing_comparator_bars",
        replacement_value_vs_cash_usd=390.84,
        replacement_value_vs_spy_usd=None,
        replacement_value_vs_qqq_usd=None,
        replacement_value_comparator_detail={"SPY": None, "QQQ": None},
    )
    state = {"closed_positions": [stale]}

    records = frv.enrich_state_closed_rows(state, BARS, "2026-06-22", "test_sleeve")

    assert len(records) == 1
    row = state["closed_positions"][0]
    assert row["replacement_value_status"] == "enriched"
    assert row["replacement_value_vs_spy_usd"] is not None
    assert row["replacement_value_vs_qqq_usd"] is not None
    assert row["replacement_value_asof"] == "2026-06-22"


def test_non_session_entry_resolves_to_prior_session_when_marked():
    state = {
        "closed_positions": [
            _row(
                entry_date="2026-05-09",
                non_session_entry_fill=True,
                non_session_entry_note="entry_date was a Saturday; filled with prior session open",
            )
        ]
    }

    records = frv.enrich_state_closed_rows(state, BARS, "2026-06-22", "test_sleeve")

    assert len(records) == 1
    detail = state["closed_positions"][0]["replacement_value_comparator_detail"]["SPY"]
    assert detail["requested_entry_date"] == "2026-05-09"
    assert detail["entry_date"] == "2026-05-08"
    assert detail["entry_date_resolution"] == "previous_session"
    assert detail["requested_exit_date"] == "2026-05-15"
    assert detail["exit_date"] == "2026-05-15"
    assert detail["exit_date_resolution"] == "exact"


def test_enrich_row_missing_bars_status():
    state = {"closed_positions": [_row(entry_date="2026-01-02", exit_date="2026-01-09")]}
    records = frv.enrich_state_closed_rows(state, BARS, "2026-06-11", "test_sleeve")
    assert records[0]["status"] == "missing_comparator_bars"
    row = state["closed_positions"][0]
    assert row["replacement_value_vs_spy_usd"] is None
    assert row["replacement_value_vs_cash_usd"] == 390.84


def test_enrich_all_sleeve_states_roundtrip(tmp_path):
    root = tmp_path / "paper_sleeves"
    sleeve_dir = root / "demo_sleeve"
    sleeve_dir.mkdir(parents=True)
    state_path = sleeve_dir / "state.json"
    state_path.write_text(json.dumps({"closed_positions": [_row()]}), encoding="utf-8")
    artifact = tmp_path / "forward_replacement_value.jsonl"

    summary = frv.enrich_all_sleeve_states(
        "2026-06-11",
        sleeves_root=root,
        bars_by_ticker=BARS,
        artifact_path=artifact,
    )
    assert summary["status"] == "ok"
    assert summary["rows_enriched"] == 1
    assert summary["sleeves"]["demo_sleeve"]["rows_enriched"] == 1
    assert summary["artifact_rows"] == 1

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["closed_positions"][0]["replacement_value_rule_version"] == frv.RULE_VERSION
    lines = [json.loads(line) for line in artifact.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 1
    assert lines[0]["sleeve_key"] == "demo_sleeve"
    assert lines[0]["status"] == "enriched"

    # idempotent second run appends nothing
    summary2 = frv.enrich_all_sleeve_states(
        "2026-06-12",
        sleeves_root=root,
        bars_by_ticker=BARS,
        artifact_path=artifact,
    )
    assert summary2["rows_enriched"] == 0
    assert summary2["artifact_rows"] == 1
    assert len(artifact.read_text(encoding="utf-8").splitlines()) == 1


def test_rebuild_current_state_artifact_removes_stale_rows_and_archives(tmp_path):
    root = tmp_path / "paper_sleeves"
    sleeve_dir = root / "demo_sleeve"
    sleeve_dir.mkdir(parents=True)
    state = {"closed_positions": [_row()]}
    frv.enrich_state_closed_rows(state, BARS, "2026-06-11", "demo_sleeve")
    (sleeve_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    current_record = frv.current_state_replacement_records(root)[0][0]
    stale_record = {
        **current_record,
        "decision_id": "STALE:removed",
        "ticker": "QQQ",
        "entry_date": "2026-05-16",
        "exit_date": "2026-05-16",
        "status": "missing_comparator_bars",
    }
    artifact = tmp_path / "forward_replacement_value.jsonl"
    artifact.write_text(
        json.dumps(current_record, sort_keys=True)
        + "\n"
        + json.dumps(stale_record, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    archive = tmp_path / "archive" / "before.jsonl"

    summary = frv.rebuild_current_state_artifact(
        sleeves_root=root,
        artifact_path=artifact,
        archive_path=archive,
    )

    rows = [json.loads(line) for line in artifact.read_text(encoding="utf-8").splitlines()]
    assert summary["previous_rows"] == 2
    assert summary["rows_written"] == 1
    assert len(summary["previous_rows_not_in_current_state"]) == 1
    assert summary["previous_rows_not_in_current_state"][0]["decision_id"] == "STALE:removed"
    assert rows == [current_record]
    assert "STALE:removed" in archive.read_text(encoding="utf-8")


def test_production_impact_is_observe_only():
    impact = frv.PRODUCTION_IMPACT
    assert impact["alters_orders"] is False
    assert impact["alters_sizing"] is False
    assert impact["alters_exits"] is False
    assert impact["alters_candidate_ranking"] is False
    assert impact["trade_enabled"] is False
