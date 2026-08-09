import ast
from datetime import date, datetime, timezone
import inspect
import json
from pathlib import Path
import sqlite3
import sys
import textwrap
import types

import pandas as pd


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import run as run_module  # noqa: E402
from fundamental_growth_rs_paper_sleeve import (  # noqa: E402
    prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot,
)
from run import (  # noqa: E402
    _build_daily_non_ohlcv_snapshot,
    _build_entry_cash_admission_observations,
    _core_slot_ticker_set,
    _persist_daily_structured_news_observation,
    _persist_drugsfda_approval_observer,
    _persist_entity_theme_news_event_forward_observer,
    _persist_entity_theme_news_observer,
    _persist_entity_theme_news_outcomes,
    _persist_estimate_revision_outcomes_after_quant_signals,
    _persist_massive_dividend_restart_forward_observer,
    _persist_massive_dividend_restart_forward_settlement,
    _persist_ortex_borrow_observer,
    _run_massive_ohlcv_grouped_catchup,
    _persist_prediction_market_event_observer,
    _persist_prediction_market_event_outcomes,
    _persist_sec_contract_relation_provenance,
    _persist_sec_corporate_event_stream,
    _persist_usaspending_obligation_observer,
    _refresh_finra_short_interest_before_coverage,
    _refresh_estimate_revision_ledger_after_quant_signals,
    _refresh_live_position_control_after_report,
    _refresh_options_forward_ledger_after_quant_signals,
    _market_run_clock,
    _resolve_options_forward_inputs,
    main,
)


def test_core_slot_ticker_set_only_includes_positive_core_slots():
    payload = {
        "core_positions": [
            {"ticker": "MRVL", "shares": 24},
            {"ticker": "ZERO", "shares": 0},
        ],
        "positions": [
            {
                "ticker": "AMZN",
                "shares": 4,
                "opened_by_strategy": "breakout_long",
            },
            {
                "ticker": "SNXX",
                "shares": 48,
                "opened_by_strategy": "fomo",
            },
            {
                "ticker": "META",
                "shares": 2,
                "slot_policy": "no_core_slot",
            },
        ],
        "observations": [
            {"ticker": "APP", "shares": 17},
        ],
    }

    assert _core_slot_ticker_set(payload) == {"AMZN", "MRVL"}


def test_core_drawdown_flow_put_observer_is_wired_default_off_daily():
    source = inspect.getsource(main)
    assert "prep_and_build_core_drawdown_flow_put_snapshot" in source
    assert "core_drawdown_flow_put_stabilization_paper_sleeve" in source
    assert "empty_core_drawdown_flow_put_snapshot" in source


def test_market_run_clock_uses_new_york_business_date():
    observed = datetime(2026, 7, 21, 1, 30, tzinfo=timezone.utc)
    market_clock = _market_run_clock(observed)
    assert market_clock.tzinfo is not None
    assert market_clock.date().isoformat() == "2026-07-20"


def test_options_forward_inputs_use_completed_session_not_latest_partial_row():
    observed = datetime(2026, 7, 31, 4, 8, tzinfo=timezone.utc)

    def frame(prior_close, partial_close):
        return pd.DataFrame(
            {"Close": [prior_close, partial_close]},
            index=pd.to_datetime(["2026-07-30", "2026-07-31"]),
        )

    resolved = _resolve_options_forward_inputs(
        _market_run_clock(observed),
        {
            "SPY": frame(700.0, 701.0),
            "QQQ": frame(620.0, 621.0),
            "TSLA": frame(300.0, 999.0),
        },
        ["SPY", "QQQ", "TSLA"],
    )

    assert resolved["quote_date"] == "2026-07-30"
    assert resolved["underlying_prices"] == {
        "QQQ": 620.0,
        "SPY": 700.0,
        "TSLA": 300.0,
    }
    assert resolved["health"]["status"] == "ok"
    assert resolved["health"]["canonical_benchmark_latest_dates"] == {
        "SPY": "2026-07-31",
        "QQQ": "2026-07-31",
    }


def test_options_forward_inputs_fail_closed_without_exact_canonical_anchors():
    observed = datetime(2026, 7, 31, 4, 8, tzinfo=timezone.utc)
    stale = pd.DataFrame(
        {"Close": [600.0]},
        index=pd.to_datetime(["2026-07-29"]),
    )

    resolved = _resolve_options_forward_inputs(
        _market_run_clock(observed),
        {"SPY": stale, "QQQ": stale, "TSLA": stale},
        ["SPY", "QQQ", "TSLA"],
    )

    assert resolved["quote_date"] is None
    assert resolved["tickers"] == []
    assert resolved["underlying_prices"] == {}
    assert resolved["health"]["status"] == "blocked"
    assert resolved["health"]["missing_exact_benchmarks"] == ["SPY", "QQQ"]


def test_cash_admission_observer_uses_structured_account_cash_without_changing_signals():
    signals = [
        {
            "ticker": "AAA",
            "strategy": "trend",
            "sizing": {"position_value_usd": 600.0},
        },
        {
            "ticker": "BBB",
            "strategy": "breakout",
            "sizing": {"position_value_usd": 500.0},
        },
    ]
    result = _build_entry_cash_admission_observations(
        signals,
        {"cash_usd": 1_000.0, "positions": []},
        {},
        as_of="2026-07-21",
    )

    assert result["status"] == "ok"
    assert result["cash_conflict_count"] == 1
    assert result["observations"][0]["cash_conflict"] is False
    assert result["observations"][1]["cash_conflict"] is True
    assert result["observations"][1]["cash_conflict_id"] == (
        "cash-conflict:2026-07-21:2:BBB"
    )
    assert result["production_impact"]["alters_orders"] is False
    assert "cash_conflict" not in signals[1]


def test_cash_admission_observer_fails_closed_without_reliable_cash():
    result = _build_entry_cash_admission_observations(
        [{"ticker": "AAA", "sizing": {"position_value_usd": 100.0}}],
        {"positions": []},
        {},
        as_of="2026-07-21",
    )
    assert result["status"] == "unavailable"
    assert result["observations"] == []


def test_fundamental_growth_rs_call_uses_core_slot_ticker_set():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    current_core_tickers_args = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", None) not in {
            "build_fundamental_growth_rs_paper_sleeve_snapshot",
            "prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot",
        }:
            continue
        for keyword in node.keywords:
            if keyword.arg == "current_core_tickers":
                current_core_tickers_args.append(keyword.value)

    assert current_core_tickers_args
    assert any(
        isinstance(value, ast.Call)
        and getattr(value.func, "id", None) == "_core_slot_ticker_set"
        for value in current_core_tickers_args
    )


def test_fundamental_growth_rs_prep_forwards_core_tickers_to_builder():
    tree = ast.parse(
        textwrap.dedent(
            inspect.getsource(prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot)
        )
    )
    current_core_tickers_args = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", None) != "build_fundamental_growth_rs_paper_sleeve_snapshot":
            continue
        for keyword in node.keywords:
            if keyword.arg == "current_core_tickers":
                current_core_tickers_args.append(keyword.value)

    assert current_core_tickers_args
    assert any(
        isinstance(value, ast.Name) and value.id == "current_core_tickers"
        for value in current_core_tickers_args
    )


def test_market_state_context_passes_universe_frames_for_breadth():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "build_readonly_market_state_context"
    ]

    assert len(calls) == 1
    universe_args = [
        keyword.value
        for keyword in calls[0].keywords
        if keyword.arg == "universe_ohlcv_by_ticker"
    ]
    assert universe_args
    assert isinstance(universe_args[0], ast.Name)
    assert universe_args[0].id == "ohlcv_dict"


def test_estimate_revision_ledger_refresh_after_quant_signals(monkeypatch):
    calls = []

    def fake_persist_estimate_revision_ledger(**kwargs):
        calls.append(kwargs)
        assert kwargs["as_of"] == "2026-07-02"
        assert kwargs["data_dir"] == "data"
        assert kwargs["output_dir"] == "data/non_ohlcv"
        assert kwargs["match_daily_signals"] is True
        return {
            "row_count": 3,
            "estimate_revision_usable_rows": 2,
            "matched_candidate_rows": 1,
            "matched_selected_signal_rows": 0,
            "daily_signal_match_record_count": 4,
            "production_impact": {
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
            },
        }

    monkeypatch.setattr(
        run_module,
        "persist_estimate_revision_ledger",
        fake_persist_estimate_revision_ledger,
    )
    snapshot = {
        "estimate_revision_ledger": {
            "row_count": 3,
            "daily_signal_match_record_count": 0,
        }
    }

    summary = _refresh_estimate_revision_ledger_after_quant_signals(
        "2026-07-02",
        snapshot,
        quant_signals_saved=True,
    )

    assert len(calls) == 1
    assert summary["matched_candidate_rows"] == 1
    assert snapshot["estimate_revision_ledger"] is summary
    assert summary["production_impact"]["alters_orders"] is False


def test_estimate_revision_ledger_refresh_skips_when_quant_signals_save_failed(
    monkeypatch,
):
    def unexpected_persist_estimate_revision_ledger(**kwargs):
        raise AssertionError("should not refresh without quant_signals")

    monkeypatch.setattr(
        run_module,
        "persist_estimate_revision_ledger",
        unexpected_persist_estimate_revision_ledger,
    )
    snapshot = {"estimate_revision_ledger": {"row_count": 3}}

    summary = _refresh_estimate_revision_ledger_after_quant_signals(
        "2026-07-02",
        snapshot,
        quant_signals_saved=False,
    )

    assert summary["status"] == "skipped"
    assert summary["reason"] == "quant_signals_save_failed"
    assert snapshot["estimate_revision_ledger"] == {"row_count": 3}
    assert summary["production_impact"]["alters_signal_generation"] is False


def test_estimate_revision_outcomes_settle_after_quant_signals(monkeypatch):
    calls = []

    def fake_materialize_estimate_revision_instrument_map(**kwargs):
        calls.append(("map", kwargs))
        assert kwargs["as_of"] == "2026-07-02"
        assert kwargs["ledger_path"].endswith("estimate_revision_ledger_20260702.jsonl")
        assert kwargs["generated_at"].tzinfo is not None
        return {"status": "ok", "added_mapping_count": 2}

    def fake_persist_estimate_revision_outcomes(**kwargs):
        calls.append(("outcomes", kwargs))
        assert kwargs["as_of"] == "2026-07-02"
        assert kwargs["data_dir"] == "data"
        assert kwargs["output_dir"] == "data/non_ohlcv"
        return {
            "status": "ok",
            "matched_candidate_rows": 3,
            "closed_rows_by_horizon": {"h0": 3, "h1": 3, "h3": 2, "h5": 0},
            "production_impact": {
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
            },
        }

    def fake_persist_recent_estimate_revision_outcome_catchup(**kwargs):
        calls.append(("catchup", kwargs))
        return {"status": "ok", "refreshed_ledger_count": 4}

    def fake_persist_estimate_revision_readiness(**kwargs):
        calls.append(("readiness", kwargs))
        assert kwargs["generated_at"].tzinfo is not None
        return {
            "status": "parked",
            "independent_decisions": 3,
            "settled_independent_decisions_by_horizon": {
                "h5": 1,
                "h10": 0,
                "h20": 0,
            },
        }

    monkeypatch.setattr(
        run_module,
        "materialize_estimate_revision_instrument_map",
        fake_materialize_estimate_revision_instrument_map,
    )
    monkeypatch.setattr(
        run_module,
        "persist_estimate_revision_outcomes",
        fake_persist_estimate_revision_outcomes,
    )
    monkeypatch.setattr(
        run_module,
        "persist_recent_estimate_revision_outcome_catchup",
        fake_persist_recent_estimate_revision_outcome_catchup,
    )
    monkeypatch.setattr(
        run_module,
        "persist_estimate_revision_readiness",
        fake_persist_estimate_revision_readiness,
    )
    snapshot = {}

    summary = _persist_estimate_revision_outcomes_after_quant_signals(
        "2026-07-02",
        snapshot,
        quant_signals_saved=True,
    )

    assert [name for name, _ in calls] == ["map", "outcomes", "catchup", "readiness"]
    assert summary["closed_rows_by_horizon"]["h3"] == 2
    assert snapshot["estimate_revision_outcomes"] is summary
    assert snapshot["estimate_revision_instrument_map"]["status"] == "ok"
    assert snapshot["estimate_revision_readiness"]["independent_decisions"] == 3
    assert summary["readiness"]["settled_independent_decisions_by_horizon"]["h20"] == 0
    assert summary["production_impact"]["alters_orders"] is False


def test_estimate_revision_outcomes_skip_when_quant_signals_save_failed(monkeypatch):
    def unexpected_persist_estimate_revision_outcomes(**kwargs):
        raise AssertionError("should not settle outcomes without quant_signals")

    monkeypatch.setattr(
        run_module,
        "persist_estimate_revision_outcomes",
        unexpected_persist_estimate_revision_outcomes,
    )
    snapshot = {"estimate_revision_outcomes": {"status": "previous"}}

    summary = _persist_estimate_revision_outcomes_after_quant_signals(
        "2026-07-02",
        snapshot,
        quant_signals_saved=False,
    )

    assert summary["status"] == "skipped"
    assert summary["reason"] == "quant_signals_save_failed"
    assert snapshot["estimate_revision_outcomes"] == {"status": "previous"}
    assert summary["production_impact"]["alters_signal_generation"] is False


def test_options_forward_ledger_refresh_after_quant_signals(monkeypatch):
    calls = []

    class FakeParser:
        def parse_args(self, argv):
            calls.append(list(argv))
            return types.SimpleNamespace(argv=list(argv))

    def fake_build_ledger(args):
        assert "--output-dir" in args.argv
        assert "data/non_ohlcv/options_forward" in args.argv
        assert "--quant-signal-dir" in args.argv
        assert "data" in args.argv
        assert "--ohlcv-snapshot" in args.argv
        assert "--ohlcv-warehouse" not in args.argv
        return {
            "mode": "default_off_forward_options_candidate_tag_ledger",
            "source_files": {
                "ohlcv_snapshot": "data/ohlcv_snapshot.json",
                "ohlcv_warehouse": None,
            },
            "candidate_summary": {
                "options_candidate_coverage_rate": 0.75,
                "quality_usable_candidates": 2,
                "outcome_status_counts": {"complete": 1, "partial_or_pending": 1},
            },
            "required_metrics": {
                "candidate_count": 4,
                "overlap_with_existing_signals": 4,
            },
            "outcome_close_summary": {"all_scoring_allowed": {"sample_size": 2}},
            "artifacts": {
                "ledger": "data/non_ohlcv/options_forward/options_forward_candidate_ledger.jsonl",
                "report": "data/non_ohlcv/options_forward/options_forward_candidate_ledger_report.json",
            },
        }

    fake_module = types.SimpleNamespace(
        build_arg_parser=lambda: FakeParser(),
        build_ledger=fake_build_ledger,
    )
    monkeypatch.setattr(
        run_module,
        "_load_options_forward_ledger_module",
        lambda: fake_module,
    )
    monkeypatch.setenv("OPTIONS_FORWARD_OHLCV_SNAPSHOT", "data/ohlcv_snapshot.json")
    snapshot = {}

    summary = _refresh_options_forward_ledger_after_quant_signals(
        "2026-07-02",
        snapshot,
        quant_signals_saved=True,
    )

    assert len(calls) == 1
    assert "--date" not in calls[0]
    assert summary["status"] == "ok"
    assert summary["candidate_count"] == 4
    assert summary["outcome_status_counts"]["complete"] == 1
    assert summary["ohlcv_snapshot"] == "data/ohlcv_snapshot.json"
    assert summary["ohlcv_warehouse"] is None
    assert snapshot["options_forward_ledger"] is summary
    assert summary["production_impact"]["alters_orders"] is False


def test_options_forward_ledger_refresh_uses_default_warehouse_when_snapshot_missing(
    monkeypatch,
):
    calls = []

    class FakeParser:
        def parse_args(self, argv):
            calls.append(list(argv))
            return types.SimpleNamespace(argv=list(argv))

    def fake_build_ledger(args):
        assert "--ohlcv-snapshot" not in args.argv
        assert "--ohlcv-warehouse" in args.argv
        assert "data/warehouse/warehouse_main.sqlite" in args.argv
        return {
            "mode": "default_off_forward_options_candidate_tag_ledger",
            "source_files": {
                "ohlcv_snapshot": None,
                "ohlcv_warehouse": "data/warehouse/warehouse_main.sqlite",
            },
            "candidate_summary": {
                "options_candidate_coverage_rate": 0.5,
                "quality_usable_candidates": 1,
                "outcome_status_counts": {"partial_or_pending": 1},
            },
            "required_metrics": {
                "candidate_count": 1,
                "overlap_with_existing_signals": 1,
            },
            "outcome_close_summary": {"all_scoring_allowed": {"sample_size": 1}},
            "artifacts": {},
        }

    fake_module = types.SimpleNamespace(
        build_arg_parser=lambda: FakeParser(),
        build_ledger=fake_build_ledger,
    )
    monkeypatch.setattr(
        run_module,
        "_load_options_forward_ledger_module",
        lambda: fake_module,
    )
    monkeypatch.setattr(
        run_module,
        "_default_options_forward_ohlcv_warehouse",
        lambda: "data/warehouse/warehouse_main.sqlite",
    )
    monkeypatch.delenv("OPTIONS_FORWARD_OHLCV_SNAPSHOT", raising=False)
    monkeypatch.delenv("OPTIONS_FORWARD_OHLCV_WAREHOUSE", raising=False)
    snapshot = {}

    summary = _refresh_options_forward_ledger_after_quant_signals(
        "2026-07-02",
        snapshot,
        quant_signals_saved=True,
    )

    assert len(calls) == 1
    assert summary["status"] == "ok"
    assert summary["candidate_count"] == 1
    assert summary["ohlcv_snapshot"] is None
    assert summary["ohlcv_warehouse"] == "data/warehouse/warehouse_main.sqlite"
    assert snapshot["options_forward_ledger"] is summary
    assert summary["production_impact"]["alters_orders"] is False


def test_options_forward_ledger_refresh_skips_when_quant_signals_save_failed(
    monkeypatch,
):
    def unexpected_loader():
        raise AssertionError("should not refresh without quant_signals")

    monkeypatch.setattr(
        run_module,
        "_load_options_forward_ledger_module",
        unexpected_loader,
    )
    snapshot = {"options_forward_ledger": {"status": "previous"}}

    summary = _refresh_options_forward_ledger_after_quant_signals(
        "2026-07-02",
        snapshot,
        quant_signals_saved=False,
    )

    assert summary["status"] == "skipped"
    assert summary["reason"] == "quant_signals_save_failed"
    assert snapshot["options_forward_ledger"] == {"status": "previous"}
    assert summary["production_impact"]["alters_signal_generation"] is False


def test_options_forward_ledger_refresh_failure_is_snapshot_visible(monkeypatch):
    class FakeParser:
        def parse_args(self, argv):
            return types.SimpleNamespace(argv=list(argv))

    def fake_build_ledger(args):
        raise RuntimeError("options ledger unavailable")

    fake_module = types.SimpleNamespace(
        build_arg_parser=lambda: FakeParser(),
        build_ledger=fake_build_ledger,
    )
    monkeypatch.setattr(
        run_module,
        "_load_options_forward_ledger_module",
        lambda: fake_module,
    )
    snapshot = {}

    summary = _refresh_options_forward_ledger_after_quant_signals(
        "2026-07-02",
        snapshot,
        quant_signals_saved=True,
    )

    assert summary["status"] == "failed_post_quant_options_forward_ledger_refresh"
    assert "options ledger unavailable" in summary["error"]
    assert snapshot["options_forward_ledger"] is summary
    assert summary["production_impact"]["alters_orders"] is False


def test_live_position_control_refresh_after_report(monkeypatch):
    calls = []

    def fake_build_position_control_ledger(**kwargs):
        calls.append(kwargs)
        assert kwargs["report_path"] == "data/daily/reports/report_20260709.txt"
        return {
            "state": {
                "status": "ok",
                "asof_date": "2026-07-09",
                "report_date": "2026-07-09",
                "positions_as_of": "2026-07-09",
                "position_rows": 2,
                "ok_to_add_reported": True,
                "ok_to_add_control_pass": False,
                "ok_to_add_control_blockers": ["exit_now"],
                "entry_slots_reported": 4,
                "manual_order_instruction_count": 3,
                "exit_now_count": 1,
                "fallback_stop_count": 0,
                "stale_target_count": 0,
                "missing_daily_report_control_count": 0,
                "report_open_positions_asof_mismatch": False,
                "ledger": {
                    "ledger_path": "data/live_pilot/position_control/ledger.jsonl",
                    "rows_appended": 2,
                    "rows_total": 2,
                },
            },
            "append_result": {
                "ledger_path": "data/live_pilot/position_control/ledger.jsonl",
                "rows_appended": 2,
                "rows_total": 2,
            },
            "rows": [{}, {}],
        }

    monkeypatch.setattr(
        run_module,
        "build_position_control_ledger",
        fake_build_position_control_ledger,
    )
    trend_signals = {}

    summary = _refresh_live_position_control_after_report(
        "2026-07-09",
        trend_signals,
        report_path="data/daily/reports/report_20260709.txt",
    )

    assert len(calls) == 1
    assert summary["status"] == "ok"
    assert summary["ok_to_add_control_pass"] is False
    assert summary["ok_to_add_control_blockers"] == ["exit_now"]
    assert summary["rows_appended"] == 2
    assert trend_signals["live_position_control"] is summary
    assert summary["production_impact"]["alters_signal_generation"] is False
    assert summary["production_impact"]["alters_candidate_ranking"] is False
    assert summary["production_impact"]["alters_sizing"] is False
    assert summary["production_impact"]["alters_orders"] is False


def test_live_position_control_refresh_skips_without_report_path(monkeypatch):
    def unexpected_build_position_control_ledger(**kwargs):
        raise AssertionError("should not refresh without a saved report path")

    monkeypatch.setattr(
        run_module,
        "build_position_control_ledger",
        unexpected_build_position_control_ledger,
    )
    trend_signals = {"live_position_control": {"status": "previous"}}

    summary = _refresh_live_position_control_after_report(
        "2026-07-09",
        trend_signals,
        report_path=None,
    )

    assert summary["status"] == "skipped"
    assert summary["reason"] == "daily_report_save_failed"
    assert trend_signals["live_position_control"] is summary
    assert summary["production_impact"]["alters_orders"] is False


def test_live_position_control_refresh_failure_is_snapshot_visible(monkeypatch):
    def failing_build_position_control_ledger(**kwargs):
        raise RuntimeError("position-control parser unavailable")

    monkeypatch.setattr(
        run_module,
        "build_position_control_ledger",
        failing_build_position_control_ledger,
    )
    trend_signals = {}

    summary = _refresh_live_position_control_after_report(
        "2026-07-09",
        trend_signals,
        report_path="data/daily/reports/report_20260709.txt",
    )

    assert summary["status"] == "failed_live_position_control_refresh"
    assert "position-control parser unavailable" in summary["error"]
    assert trend_signals["live_position_control"] is summary
    assert summary["production_impact"]["alters_orders"] is False


def test_daily_non_ohlcv_wires_form4_context_into_run_path(monkeypatch):
    calls = {"ensure": [], "fallback": []}

    def fake_ensure_non_ohlcv_coverage(**kwargs):
        calls["ensure"].append(kwargs)
        return {
            "profile": "daily",
            "days_total": 1,
            "days_generated": 1,
            "days_recorded_existing": 0,
            "days_failed": 0,
            "errors": [],
            "daily_snapshots": {},
        }

    def fake_persist_daily_non_ohlcv_snapshots(**kwargs):
        calls["fallback"].append(kwargs)
        return {
            "status": "ok",
            "form4_sale_overhang_context": {
                "status": "ok",
                "rows_written": 2,
                "trade_enabled": False,
                "daily_snapshot_wired": True,
                "production_impact": {
                    "alters_signal_generation": False,
                    "alters_candidate_ranking": False,
                    "alters_sizing": False,
                    "alters_orders": False,
                },
            },
        }

    monkeypatch.setitem(
        sys.modules,
        "backfill_non_ohlcv",
        types.SimpleNamespace(ensure_non_ohlcv_coverage=fake_ensure_non_ohlcv_coverage),
    )
    monkeypatch.setitem(
        sys.modules,
        "daily_non_ohlcv_snapshot",
        types.SimpleNamespace(
            persist_daily_non_ohlcv_snapshots=fake_persist_daily_non_ohlcv_snapshots
        ),
    )

    snapshot = _build_daily_non_ohlcv_snapshot(
        today=date(2026, 7, 4),
        today_iso="2026-07-04",
        data_universe=["CRDO"],
        options_ingest_tickers=["CRDO"],
        option_underlying_prices={"CRDO": 1.0},
        options_quote_date="2026-07-02",
        options_collection_health={
            "status": "ok",
            "completed_session_date": "2026-07-02",
        },
        non_ohlcv_catchup_summary={"status": "ok", "days_total": 0},
    )

    assert calls["ensure"]
    assert calls["ensure"][0]["profile"] == "daily"
    assert calls["ensure"][0]["refresh_form4_context"] is True
    assert calls["ensure"][0]["options_quote_date"] == "2026-07-02"
    assert calls["ensure"][0]["options_collection_health"]["status"] == "ok"
    assert calls["fallback"]
    assert calls["fallback"][0]["refresh_form4_context"] is True
    assert calls["fallback"][0]["refresh_options"] is True
    assert calls["fallback"][0]["options_quote_date"] == "2026-07-02"
    form4_context = snapshot["form4_sale_overhang_context"]
    assert form4_context["trade_enabled"] is False
    impact = form4_context["production_impact"]
    assert impact["alters_signal_generation"] is False
    assert impact["alters_candidate_ranking"] is False
    assert impact["alters_sizing"] is False
    assert impact["alters_orders"] is False


def test_finra_archive_refresh_precedes_coverage_and_uses_broad_universe(monkeypatch):
    calls = []
    old_rows = [
        {
            "ticker": "AAA",
            "publication_date": "2026-07-10",
            "settlement_date": "2026-06-30",
        }
    ]
    new_rows = old_rows + [
        {
            "ticker": "BBB",
            "publication_date": "2026-07-24",
            "settlement_date": "2026-07-15",
        },
        {
            "ticker": "CCC",
            "publication_date": "2026-07-24",
            "settlement_date": "2026-07-15",
        },
    ]

    def fake_refresh(**kwargs):
        calls.append(kwargs)
        return new_rows, "local_archive_refreshed", [{"publication_date": "2026-07-24"}]

    monkeypatch.setitem(
        sys.modules,
        "finra_iwm_paper_sleeve",
        types.SimpleNamespace(
            load_finra_short_interest_rows=lambda: old_rows,
            refresh_finra_short_interest_archive=fake_refresh,
        ),
    )

    summary = _refresh_finra_short_interest_before_coverage(
        today_iso="2026-07-27",
        tickers=["aaa", "BBB", "CCC"],
    )

    assert calls[0]["tickers"] == {"AAA", "BBB", "CCC"}
    assert calls[0]["as_of"] == "2026-07-27"
    assert calls[0]["max_staleness_days"] == -1
    assert summary["status"] == "ok"
    assert summary["source_status"] == "local_archive_refreshed"
    assert summary["publication_date_max"] == "2026-07-24"
    assert summary["settlement_date_max"] == "2026-07-15"
    assert summary["latest_settlement_ticker_count"] == 2
    assert summary["latest_settlement_fraction_of_requested_universe"] == 0.666667
    assert summary["density_forced_refresh"] is True
    assert summary["archive_changed"] is True
    assert summary["production_impact"]["alters_signal_generation"] is False
    assert summary["production_impact"]["alters_candidate_ranking"] is False
    assert summary["production_impact"]["alters_sizing"] is False
    assert summary["production_impact"]["alters_orders"] is False


def test_finra_precoverage_refresh_is_fail_soft(monkeypatch):
    def failing_refresh(**_kwargs):
        raise RuntimeError("synthetic FINRA outage")

    monkeypatch.setitem(
        sys.modules,
        "finra_iwm_paper_sleeve",
        types.SimpleNamespace(
            load_finra_short_interest_rows=lambda: [],
            refresh_finra_short_interest_archive=failing_refresh,
        ),
    )

    summary = _refresh_finra_short_interest_before_coverage(
        today_iso="2026-07-27",
        tickers=["AAA"],
    )

    assert summary["status"] == "unavailable"
    assert summary["reason"] == "finra_precoverage_refresh_failed"
    assert "synthetic FINRA outage" in summary["error"]
    assert summary["production_impact"]["alters_orders"] is False


def test_main_refreshes_finra_archive_before_non_ohlcv_coverage():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    calls = {
        getattr(node.func, "id", None): node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None)
        in {
            "_refresh_finra_short_interest_before_coverage",
            "_build_daily_non_ohlcv_snapshot",
            "prep_and_build_sec_ftd_finra_paper_sleeve_snapshot",
        }
    }

    refresh_call = calls["_refresh_finra_short_interest_before_coverage"]
    coverage_call = calls["_build_daily_non_ohlcv_snapshot"]
    sleeve_call = calls["prep_and_build_sec_ftd_finra_paper_sleeve_snapshot"]
    assert refresh_call.lineno < coverage_call.lineno < sleeve_call.lineno
    ticker_args = [
        keyword.value for keyword in refresh_call.keywords if keyword.arg == "tickers"
    ]
    assert len(ticker_args) == 1
    assert isinstance(ticker_args[0], ast.Name)
    assert ticker_args[0].id == "broad_ingest_universe"


def _install_fake_ortex_wiring_modules(monkeypatch, observer):
    def fake_is_us_equity_session(value):
        return date.fromisoformat(str(value)[:10]).weekday() < 5

    monkeypatch.setitem(sys.modules, "ortex_borrow_observer", observer)
    monkeypatch.setitem(
        sys.modules,
        "us_market_calendar",
        types.SimpleNamespace(is_us_equity_session=fake_is_us_equity_session),
    )


def test_ortex_borrow_observer_daily_wiring_refreshes_once_with_bounded_contract(
    monkeypatch, tmp_path
):
    calls = []

    def fake_cycle(**kwargs):
        calls.append(kwargs)
        return {
            "observer_name": "ortex_cost_to_borrow_new_observer",
            "as_of": kwargs["as_of"],
            "source_row_count": 20,
            "snapshot": {"as_of": kwargs["as_of"], "coverage_count": 20},
            "outcome_summary": {"settled_count": 40},
            "network_refresh": {"status": "ok", "requests_made": 4},
            "trade_enabled": False,
        }

    observer = types.SimpleNamespace(
        run_ortex_borrow_observer_cycle=fake_cycle,
        LATEST_SNAPSHOT_PATH=tmp_path / "latest.json",
        SNAPSHOT_LEDGER_PATH=tmp_path / "snapshots.jsonl",
    )
    _install_fake_ortex_wiring_modules(monkeypatch, observer)
    monkeypatch.delenv("ORTEX_BORROW_REFRESH_DISABLED", raising=False)
    snapshot = {}
    spy_rows = [
        {"Date": "2026-07-02", "Open": 100.0, "Close": 101.0},
        {"Date": "2026-07-06", "Open": 101.0, "Close": 102.0},
    ]
    qqq_rows = [{"Date": "2026-07-06", "Open": 200.0, "Close": 201.0}]

    result = _persist_ortex_borrow_observer(
        today_iso="2026-07-06",
        non_ohlcv_snapshot=snapshot,
        ohlcv_dict={"AAPL": spy_rows},
        spy_ohlcv=spy_rows,
        qqq_ohlcv=qqq_rows,
    )

    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["refresh_network"] is True
    assert kwargs["max_refresh_tickers"] == 4
    assert kwargs["min_refresh_age_days"] == 5
    assert kwargs["credit_budget"] == 50
    assert kwargs["min_credits_left"] == 250
    assert kwargs["price_history_by_ticker"]["SPY"] is spy_rows
    assert kwargs["price_history_by_ticker"]["QQQ"] is qqq_rows
    assert "2026-07-02" in kwargs["trading_dates"]
    assert "2026-07-20" in kwargs["trading_dates"]
    assert snapshot["ortex_borrow_observer"] is result
    assert result["trade_enabled"] is False
    assert result["production_impact"]["alters_signal_generation"] is False
    assert result["production_impact"]["alters_candidate_ranking"] is False
    assert result["production_impact"]["alters_sizing"] is False
    assert result["production_impact"]["alters_orders"] is False


def test_ortex_borrow_observer_daily_wiring_honors_network_opt_out(
    monkeypatch, tmp_path
):
    calls = []

    def fake_cycle(**kwargs):
        calls.append(kwargs)
        return {"as_of": kwargs["as_of"], "network_refresh": {"status": "disabled"}}

    observer = types.SimpleNamespace(
        run_ortex_borrow_observer_cycle=fake_cycle,
        LATEST_SNAPSHOT_PATH=tmp_path / "latest.json",
        SNAPSHOT_LEDGER_PATH=tmp_path / "snapshots.jsonl",
    )
    _install_fake_ortex_wiring_modules(monkeypatch, observer)
    monkeypatch.setenv("ORTEX_BORROW_REFRESH_DISABLED", "true")

    _persist_ortex_borrow_observer(
        today_iso="2026-07-06",
        non_ohlcv_snapshot={},
        ohlcv_dict={"SPY": [{"Date": "2026-07-06"}]},
    )

    assert len(calls) == 1
    assert calls[0]["refresh_network"] is False


def test_ortex_borrow_observer_daily_wiring_does_not_refetch_existing_snapshot(
    monkeypatch, tmp_path
):
    calls = []

    def fake_cycle(**kwargs):
        calls.append(kwargs)
        return {"as_of": kwargs["as_of"], "network_refresh": {"status": "disabled"}}

    latest_path = tmp_path / "latest.json"
    latest_path.write_text('{"as_of":"2026-07-06"}', encoding="utf-8")
    observer = types.SimpleNamespace(
        run_ortex_borrow_observer_cycle=fake_cycle,
        LATEST_SNAPSHOT_PATH=latest_path,
        SNAPSHOT_LEDGER_PATH=tmp_path / "snapshots.jsonl",
    )
    _install_fake_ortex_wiring_modules(monkeypatch, observer)
    monkeypatch.delenv("ORTEX_BORROW_REFRESH_DISABLED", raising=False)

    _persist_ortex_borrow_observer(
        today_iso="2026-07-06",
        non_ohlcv_snapshot={},
        ohlcv_dict={"SPY": [{"Date": "2026-07-06"}]},
    )

    assert len(calls) == 1
    assert calls[0]["refresh_network"] is False


def test_ortex_borrow_observer_daily_wiring_is_fail_open_and_order_inert(monkeypatch):
    def failing_cycle(**kwargs):
        raise RuntimeError("synthetic ORTEX outage")

    _install_fake_ortex_wiring_modules(
        monkeypatch,
        types.SimpleNamespace(run_ortex_borrow_observer_cycle=failing_cycle),
    )
    snapshot = {"existing": "preserved"}

    result = _persist_ortex_borrow_observer(
        today_iso="2026-07-06",
        non_ohlcv_snapshot=snapshot,
        ohlcv_dict={"SPY": [{"Date": "2026-07-06"}]},
    )

    assert snapshot["existing"] == "preserved"
    assert snapshot["ortex_borrow_observer"] is result
    assert result["status"] == "failed_ortex_borrow_observer"
    assert "synthetic ORTEX outage" in result["error"]
    assert result["trade_enabled"] is False
    assert result["strategy_behavior_changed"] is False
    assert result["alters_orders"] is False
    assert result["production_impact"]["alters_orders"] is False


def test_main_mounts_ortex_observer_after_non_ohlcv_snapshot_build():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "_persist_ortex_borrow_observer"
    ]

    assert len(calls) == 1
    keyword_names = {keyword.arg for keyword in calls[0].keywords}
    assert keyword_names == {
        "today_iso",
        "non_ohlcv_snapshot",
        "ohlcv_dict",
        "spy_ohlcv",
        "qqq_ohlcv",
    }


def test_structured_news_observation_runs_second_order_exposure_observer(monkeypatch):
    calls = {"snapshot": 0, "observer": 0}

    def fake_snapshot(today):
        calls["snapshot"] += 1
        assert today == "20260702"
        return {
            "event_contract_audit": {"ledger_rows": 3},
            "forward_observation_contract_audit": {
                "observation_rows": 9,
                "target_relation_quality_rows": 4,
            },
            "strategy_behavior_changed": False,
            "trade_enabled": False,
        }

    def fake_observer_run():
        calls["observer"] += 1
        return {
            "rows": 11,
            "closed_rows": 5,
            "pending_rows": 6,
            "appended_this_run": 2,
        }

    monkeypatch.setitem(
        sys.modules,
        "daily_news_structured_event_snapshot",
        types.SimpleNamespace(persist_daily_structured_event_snapshot=fake_snapshot),
    )
    monkeypatch.setitem(
        sys.modules,
        "news_event_exposure_observer",
        types.SimpleNamespace(run=fake_observer_run),
    )

    snapshot = _persist_daily_structured_news_observation("20260702")

    assert calls == {"snapshot": 1, "observer": 1}
    assert snapshot["strategy_behavior_changed"] is False
    assert snapshot["trade_enabled"] is False
    assert snapshot["second_order_exposure_observer"]["rows"] == 11


def test_structured_news_observation_keeps_snapshot_when_exposure_observer_fails(
    monkeypatch,
):
    def fake_snapshot(today):
        return {
            "event_contract_audit": {"ledger_rows": 1},
            "forward_observation_contract_audit": {
                "observation_rows": 1,
                "target_relation_quality_rows": 1,
            },
            "strategy_behavior_changed": False,
            "trade_enabled": False,
        }

    def failing_observer_run():
        raise RuntimeError("observer unavailable")

    monkeypatch.setitem(
        sys.modules,
        "daily_news_structured_event_snapshot",
        types.SimpleNamespace(persist_daily_structured_event_snapshot=fake_snapshot),
    )
    monkeypatch.setitem(
        sys.modules,
        "news_event_exposure_observer",
        types.SimpleNamespace(run=failing_observer_run),
    )

    snapshot = _persist_daily_structured_news_observation("20260702")

    assert snapshot["strategy_behavior_changed"] is False
    assert snapshot["trade_enabled"] is False
    assert snapshot["second_order_exposure_observer"]["status"] == "unavailable"
    assert "observer unavailable" in snapshot["second_order_exposure_observer"]["error"]


def test_sec_corporate_event_stream_daily_wiring(monkeypatch):
    calls = {"ingest": 0, "ticker_map": 0}

    def fake_load_company_ticker_map():
        calls["ticker_map"] += 1
        return {"0001675149": {"ticker": "AA"}}

    def fake_ingest_range(start, end, **kwargs):
        calls["ingest"] += 1
        assert start == date(2026, 7, 1)
        assert end == date(2026, 7, 2)
        assert kwargs["today"] == date(2026, 7, 2)
        assert kwargs["sleep_seconds"] == 0.0
        assert kwargs["ticker_map"] == {"0001675149": {"ticker": "AA"}}
        return {
            "quarters_considered": 1,
            "quarters_fetched": 1,
            "rows_appended": 2,
            "rows_path": "data/non_ohlcv/sec_corporate_event_stream/rows.jsonl",
        }

    monkeypatch.setitem(
        sys.modules,
        "sec_ticker_map",
        types.SimpleNamespace(load_company_ticker_map=fake_load_company_ticker_map),
    )
    monkeypatch.setitem(
        sys.modules,
        "sec_corporate_event_stream",
        types.SimpleNamespace(ingest_range=fake_ingest_range),
    )

    summary = _persist_sec_corporate_event_stream("20260702")

    assert calls == {"ingest": 1, "ticker_map": 1}
    assert summary["status"] == "ok"
    assert summary["rows_appended"] == 2
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False


def test_sec_corporate_event_stream_daily_wiring_fail_soft(monkeypatch):
    def failing_ingest_range(start, end, **kwargs):
        raise RuntimeError("sec unavailable")

    monkeypatch.setitem(
        sys.modules,
        "sec_ticker_map",
        types.SimpleNamespace(load_company_ticker_map=lambda: {}),
    )
    monkeypatch.setitem(
        sys.modules,
        "sec_corporate_event_stream",
        types.SimpleNamespace(ingest_range=failing_ingest_range),
    )

    summary = _persist_sec_corporate_event_stream("20260702")

    assert summary["status"] == "unavailable"
    assert "sec unavailable" in summary["error"]
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False


def test_sec_contract_relation_provenance_daily_wiring(monkeypatch):
    calls = {"persist": 0}

    def fake_persist_sec_contract_relation_provenance(today):
        calls["persist"] += 1
        assert today == "20260703"
        return {
            "status": "ok",
            "input_row_count": 7,
            "item_101_input_row_count": 3,
            "provenance_row_count": 5,
            "rows_appended": 2,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
        }

    monkeypatch.setitem(
        sys.modules,
        "sec_contract_relation_provenance",
        types.SimpleNamespace(
            persist_sec_contract_relation_provenance=(
                fake_persist_sec_contract_relation_provenance
            )
        ),
    )

    summary = _persist_sec_contract_relation_provenance("20260703")

    assert calls == {"persist": 1}
    assert summary["status"] == "ok"
    assert summary["provenance_row_count"] == 5
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False


def test_sec_contract_relation_provenance_daily_wiring_fail_soft(monkeypatch):
    def failing_persist_sec_contract_relation_provenance(today):
        raise RuntimeError("contract relation surface unavailable")

    monkeypatch.setitem(
        sys.modules,
        "sec_contract_relation_provenance",
        types.SimpleNamespace(
            persist_sec_contract_relation_provenance=(
                failing_persist_sec_contract_relation_provenance
            )
        ),
    )

    summary = _persist_sec_contract_relation_provenance("20260703")

    assert summary["status"] == "unavailable"
    assert "contract relation surface unavailable" in summary["error"]
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False


def test_entity_theme_news_observer_daily_wiring(monkeypatch):
    calls = {"persist": 0}

    def fake_persist_entity_theme_news_observer(today):
        calls["persist"] += 1
        assert today == "20260703"
        return {
            "status": "ok",
            "source_count": 6,
            "raw_item_count": 12,
            "unique_item_count": 10,
            "source_error_count": 0,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
        }

    monkeypatch.setitem(
        sys.modules,
        "entity_theme_news_observer",
        types.SimpleNamespace(
            persist_entity_theme_news_observer=fake_persist_entity_theme_news_observer
        ),
    )

    summary = _persist_entity_theme_news_observer("20260703")

    assert calls == {"persist": 1}
    assert summary["status"] == "ok"
    assert summary["source_count"] == 6
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False


def test_entity_theme_news_observer_daily_wiring_fail_soft(monkeypatch):
    def failing_persist_entity_theme_news_observer(today):
        raise RuntimeError("entity observer unavailable")

    monkeypatch.setitem(
        sys.modules,
        "entity_theme_news_observer",
        types.SimpleNamespace(
            persist_entity_theme_news_observer=failing_persist_entity_theme_news_observer
        ),
    )

    summary = _persist_entity_theme_news_observer("20260703")

    assert summary["status"] == "unavailable"
    assert "entity observer unavailable" in summary["error"]
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False


def test_entity_theme_news_event_forward_observer_daily_wiring(monkeypatch):
    calls = {"persist": 0}

    def fake_persist_entity_theme_news_event_forward_observer(today):
        calls["persist"] += 1
        assert today == "20260703"
        return {
            "status": "ok",
            "decision_count": 7,
            "rows_appended": 5,
            "settled_count": 2,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
        }

    monkeypatch.setitem(
        sys.modules,
        "entity_theme_news_event_forward_observer",
        types.SimpleNamespace(
            persist_entity_theme_news_event_forward_observer=(
                fake_persist_entity_theme_news_event_forward_observer
            )
        ),
    )

    summary = _persist_entity_theme_news_event_forward_observer("20260703")

    assert calls == {"persist": 1}
    assert summary["status"] == "ok"
    assert summary["decision_count"] == 7
    assert summary["rows_appended"] == 5
    assert summary["settled_count"] == 2
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False


def test_entity_theme_news_event_forward_observer_daily_wiring_fail_soft(monkeypatch):
    def failing_persist_entity_theme_news_event_forward_observer(today):
        raise RuntimeError("entity theme event forward observer unavailable")

    monkeypatch.setitem(
        sys.modules,
        "entity_theme_news_event_forward_observer",
        types.SimpleNamespace(
            persist_entity_theme_news_event_forward_observer=(
                failing_persist_entity_theme_news_event_forward_observer
            )
        ),
    )

    summary = _persist_entity_theme_news_event_forward_observer("20260703")

    assert summary["status"] == "unavailable"
    assert "entity theme event forward observer unavailable" in summary["error"]
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False


def test_drugsfda_approval_observer_produces_before_consuming_and_reports_coverage(
    monkeypatch, tmp_path
):
    raw_zip_path = tmp_path / "drugsatfda_official.zip"
    raw_zip_path.write_bytes(b"official fixture")
    manifest_path = tmp_path / "snapshot_manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    calls = {"producer": [], "observer": [], "health": []}

    def fake_fetch_daily_drugsfda_snapshot(today):
        calls["producer"].append(today)
        return {
            "status": "ok",
            "producer_mode": "official_daily_drugsfda_download",
            "source_mode": "official_producer",
            "snapshot_path": str(raw_zip_path),
            "manifest_path": str(manifest_path),
            "retrieved_at_utc": "2026-07-28T12:00:00Z",
        }

    def fake_persist_daily_drugsfda_approval_observer(**kwargs):
        calls["observer"].append(kwargs)
        return {
            "status": "ok",
            "parsed_application_count": 17,
            "rows_appended": 0,
            "new_forward_event_count": 0,
            "forward_event_count_total": 0,
        }

    def fake_persist_producer_health_summary(**kwargs):
        calls["health"].append(kwargs)
        return {
            **kwargs["observer_summary"],
            "status": "ok",
            "producer_health_status": "ok",
            "heartbeat_status": "fresh_success_zero_forward",
            "snapshot_fresh": True,
            "zero_event_heartbeat": True,
        }

    monkeypatch.delenv("GINGER_DRUGSFDA_APPROVAL_SNAPSHOT", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "drugsfda_approval_observer",
        types.SimpleNamespace(
            fetch_daily_drugsfda_snapshot=fake_fetch_daily_drugsfda_snapshot,
            persist_daily_drugsfda_approval_observer=(
                fake_persist_daily_drugsfda_approval_observer
            ),
            persist_producer_health_summary=fake_persist_producer_health_summary,
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_drugsfda_approval_observer(
        "20260728", non_ohlcv_snapshot
    )

    assert calls["producer"] == ["20260728"]
    assert calls["observer"] == [
        {
            "today": "20260728",
            "raw_zip_path": str(raw_zip_path),
            "snapshot_manifest_path": str(manifest_path),
            "observed_at": "2026-07-28T12:00:00Z",
        }
    ]
    assert len(calls["health"]) == 1
    assert summary["status"] == "ok"
    assert summary["zero_event_heartbeat"] is True
    assert non_ohlcv_snapshot["coverage_manifest"][
        "drugsfda_approval_observer"
    ]["heartbeat_status"] == "fresh_success_zero_forward"
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False
    assert summary["alters_orders"] is False
    assert summary["alters_signal_generation"] is False
    assert summary["alters_candidate_ranking"] is False
    assert summary["alters_ranking"] is False
    assert summary["alters_sizing"] is False
    assert summary["alters_exits"] is False


def test_drugsfda_approval_observer_missing_override_fails_closed(
    monkeypatch, tmp_path
):
    observer_calls = []
    health_calls = []
    raw_zip_path = tmp_path / "missing_drugsatfda_official.zip"

    def unexpected_persist_daily_drugsfda_approval_observer(**kwargs):
        observer_calls.append(kwargs)

    def unexpected_fetch(*_args, **_kwargs):
        raise AssertionError("configured override must not fetch")

    def fake_persist_producer_health_summary(**kwargs):
        health_calls.append(kwargs)
        return {
            "status": "unavailable",
            "reason": "producer_unavailable",
            "producer_health_status": "unavailable",
            "snapshot_fresh": False,
        }

    monkeypatch.setenv("GINGER_DRUGSFDA_APPROVAL_SNAPSHOT", str(raw_zip_path))
    monkeypatch.setitem(
        sys.modules,
        "drugsfda_approval_observer",
        types.SimpleNamespace(
            fetch_daily_drugsfda_snapshot=unexpected_fetch,
            persist_daily_drugsfda_approval_observer=(
                unexpected_persist_daily_drugsfda_approval_observer
            ),
            persist_producer_health_summary=fake_persist_producer_health_summary,
        ),
    )

    summary = _persist_drugsfda_approval_observer("20260713")

    assert observer_calls == []
    assert len(health_calls) == 1
    assert summary["status"] == "unavailable"
    assert summary["reason"] == "producer_unavailable"
    assert summary["snapshot_fresh"] is False
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False
    assert summary["alters_orders"] is False
    assert summary["alters_signal_generation"] is False
    assert summary["alters_candidate_ranking"] is False
    assert summary["alters_ranking"] is False
    assert summary["alters_sizing"] is False
    assert summary["alters_exits"] is False


def test_drugsfda_approval_observer_daily_wiring_fail_soft(monkeypatch, tmp_path):
    raw_zip_path = tmp_path / "drugsatfda_official.zip"
    raw_zip_path.write_bytes(b"official fixture")
    calls = []
    health_calls = []

    def fake_fetch_daily_drugsfda_snapshot(today):
        return {
            "status": "ok",
            "producer_mode": "official_daily_drugsfda_download",
            "source_mode": "official_producer",
            "snapshot_path": str(raw_zip_path),
            "manifest_path": str(tmp_path / "manifest.json"),
            "retrieved_at_utc": "2026-07-13T12:00:00Z",
        }

    def failing_persist_daily_drugsfda_approval_observer(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("Drugs@FDA observer unavailable")

    def fake_persist_producer_health_summary(**kwargs):
        health_calls.append(kwargs)
        return {
            "status": "unavailable",
            "reason": "observer_or_producer_error",
            "error": kwargs.get("error"),
        }

    monkeypatch.delenv("GINGER_DRUGSFDA_APPROVAL_SNAPSHOT", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "drugsfda_approval_observer",
        types.SimpleNamespace(
            fetch_daily_drugsfda_snapshot=fake_fetch_daily_drugsfda_snapshot,
            persist_daily_drugsfda_approval_observer=(
                failing_persist_daily_drugsfda_approval_observer
            ),
            persist_producer_health_summary=fake_persist_producer_health_summary,
        ),
    )

    summary = _persist_drugsfda_approval_observer("20260713")

    assert calls == [
        {
            "today": "20260713",
            "raw_zip_path": str(raw_zip_path),
            "snapshot_manifest_path": str(tmp_path / "manifest.json"),
            "observed_at": "2026-07-13T12:00:00Z",
        }
    ]
    assert summary["status"] == "unavailable"
    assert "Drugs@FDA observer unavailable" in summary["error"]
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False
    assert summary["alters_orders"] is False
    assert summary["alters_ranking"] is False
    assert summary["alters_sizing"] is False
    assert summary["alters_exits"] is False


def test_drugsfda_approval_observer_is_wired_in_both_daily_paths():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    call_expressions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None)
        == "_persist_drugsfda_approval_observer"
    ]

    assert len(call_expressions) == 2
    assert all(
        isinstance(expression.value, ast.Call)
        and len(expression.value.args) == 2
        and isinstance(expression.value.args[0], ast.Name)
        and expression.value.args[0].id == "today"
        and isinstance(expression.value.args[1], ast.Name)
        and expression.value.args[1].id == "non_ohlcv_snapshot"
        for expression in call_expressions
    )


def test_usaspending_obligation_observer_preserves_local_snapshot_override(
    monkeypatch, tmp_path
):
    snapshot_path = tmp_path / "usaspending_transactions.json"
    snapshot_path.write_text("{}", encoding="utf-8")
    observer_calls = []
    health_calls = []

    def fake_run_observer(**kwargs):
        observer_calls.append(kwargs)
        return {
            "status": "ok",
            "parsed_transaction_count": 23,
            "rows_appended": 4,
            "new_forward_rows_appended": 4,
            "strategy_behavior_changed": True,
            "trade_enabled": True,
            "alters_orders": True,
        }

    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("configured local override must not call the producer")

    def fake_persist_health(**kwargs):
        health_calls.append(kwargs)
        return {
            **dict(kwargs.get("observer_summary") or {}),
            "status": "stale",
            "reason": "unverified_local_override",
            "producer_status": "unverified",
            "producer_mode": kwargs["producer_result"]["producer_mode"],
            "snapshot_fresh": False,
        }

    monkeypatch.setenv(
        "GINGER_USASPENDING_TRANSACTION_SNAPSHOT",
        str(snapshot_path),
    )
    monkeypatch.setitem(
        sys.modules,
        "usaspending_obligation_observer",
        types.SimpleNamespace(
            fetch_daily_transaction_snapshot=unexpected_fetch,
            persist_producer_health_summary=fake_persist_health,
            run_observer=fake_run_observer,
        ),
    )

    summary = _persist_usaspending_obligation_observer("20260713")

    assert observer_calls == [
        {
            "snapshot_path": str(snapshot_path),
            "observed_at": None,
        }
    ]
    assert health_calls[0]["producer_result"]["producer_mode"] == "configured_local_snapshot"
    assert summary["status"] == "stale"
    assert summary["snapshot_fresh"] is False
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False
    assert summary["alters_orders"] is False
    assert summary["alters_ranking"] is False
    assert summary["alters_sizing"] is False
    assert summary["alters_exits"] is False


def test_usaspending_obligation_observer_fetches_official_snapshot_without_override(
    monkeypatch, tmp_path
):
    snapshot_path = tmp_path / "usaspending_transactions.zip"
    snapshot_path.write_bytes(b"PK-test")
    calls = {"fetch": [], "observer": [], "health": []}

    def fake_fetch(run_date):
        calls["fetch"].append(run_date)
        return {
            "status": "ok",
            "producer_mode": "official_daily_download",
            "snapshot_path": str(snapshot_path),
            "retrieved_at_utc": "2026-07-13T20:52:47Z",
            "manifest_path": str(tmp_path / "manifest.json"),
        }

    def fake_run_observer(**kwargs):
        calls["observer"].append(kwargs)
        return {
            "status": "ok",
            "rows_appended": 0,
            "new_forward_rows_appended": 0,
            "new_eligible_forward_rows_appended": 0,
            "forward_event_count_total": 0,
            "eligible_forward_event_count_total": 0,
        }

    def fake_persist_health(**kwargs):
        calls["health"].append(kwargs)
        return {
            **dict(kwargs["observer_summary"]),
            "status": "ok",
            "producer_status": "ok",
            "producer_mode": "official_daily_download",
            "run_date": "2026-07-13",
            "retrieved_at_utc": "2026-07-13T20:52:47Z",
            "snapshot_fresh": True,
            "snapshot_age_days": 0,
            "heartbeat_status": "fresh_success_zero_forward",
            "zero_event_heartbeat": True,
        }

    monkeypatch.delenv("GINGER_USASPENDING_TRANSACTION_SNAPSHOT", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "usaspending_obligation_observer",
        types.SimpleNamespace(
            fetch_daily_transaction_snapshot=fake_fetch,
            persist_producer_health_summary=fake_persist_health,
            run_observer=fake_run_observer,
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_usaspending_obligation_observer(
        "20260713", non_ohlcv_snapshot
    )

    assert calls["fetch"] == ["20260713"]
    assert calls["observer"] == [
        {
            "snapshot_path": str(snapshot_path),
            "observed_at": "2026-07-13T20:52:47Z",
        }
    ]
    assert len(calls["health"]) == 1
    assert summary["status"] == "ok"
    assert summary["zero_event_heartbeat"] is True
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False
    assert non_ohlcv_snapshot["coverage_manifest"][
        "usaspending_obligation_observer"
    ]["heartbeat_status"] == "fresh_success_zero_forward"


def test_usaspending_obligation_observer_exposes_pending_resume_health(
    monkeypatch,
):
    producer = {
        "status": "pending",
        "producer_mode": "official_daily_transaction_download",
        "source_mode": "official_producer",
        "run_date": "2026-07-13",
        "job_requested_at_utc": "2026-07-13T20:52:00Z",
        "status_poll_count": 15,
        "attempt_poll_count": 15,
        "resumed_pending_job": True,
        "pending_job_validation_status": "validated",
        "error": "USAspending status poll budget exhausted",
    }
    health_calls = []

    def fake_persist_health(**kwargs):
        health_calls.append(kwargs)
        return {
            **producer,
            "reason": "producer_pending",
            "producer_status": "pending",
            "producer_health_status": "pending",
            "producer_job_requested_at_utc": producer["job_requested_at_utc"],
            "producer_status_poll_count": producer["status_poll_count"],
            "producer_attempt_poll_count": producer["attempt_poll_count"],
        }

    def unexpected_observer(**_kwargs):
        raise AssertionError("pending producer must not run the observer")

    monkeypatch.delenv("GINGER_USASPENDING_TRANSACTION_SNAPSHOT", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "usaspending_obligation_observer",
        types.SimpleNamespace(
            fetch_daily_transaction_snapshot=lambda _today: producer,
            persist_producer_health_summary=fake_persist_health,
            run_observer=unexpected_observer,
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_usaspending_obligation_observer(
        "20260713", non_ohlcv_snapshot
    )
    coverage = non_ohlcv_snapshot["coverage_manifest"][
        "usaspending_obligation_observer"
    ]

    assert len(health_calls) == 1
    assert summary["status"] == "pending"
    assert summary["trade_enabled"] is False
    assert coverage["resumed_pending_job"] is True
    assert coverage["pending_job_validation_status"] == "validated"
    assert coverage["producer_job_requested_at_utc"] == "2026-07-13T20:52:00Z"
    assert coverage["producer_status_poll_count"] == 15
    assert coverage["producer_attempt_poll_count"] == 15


def test_usaspending_daily_wiring_blocks_current_day_behind_prior_pending(
    monkeypatch,
):
    producer = {
        "status": "pending",
        "producer_mode": "official_daily_transaction_download",
        "source_mode": "official_producer",
        "run_date": "2026-07-29",
        "job_requested_at_utc": "2026-07-30T03:08:17Z",
        "status_poll_count": 16,
        "attempt_poll_count": 1,
        "resumed_pending_job": True,
        "pending_job_validation_status": "validated",
        "error": "USAspending status poll budget exhausted",
    }
    fetch_calls = []
    health_calls = []

    def fake_fetch(run_date):
        fetch_calls.append(run_date)
        return producer

    def fake_health(**kwargs):
        health_calls.append(kwargs)
        return {
            **producer,
            "reason": "producer_pending",
            "producer_status": "pending",
            "producer_health_status": "pending",
        }

    def unexpected_observer(**_kwargs):
        raise AssertionError("a prior pending job must block current-day consumption")

    monkeypatch.delenv("GINGER_USASPENDING_TRANSACTION_SNAPSHOT", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "usaspending_obligation_observer",
        types.SimpleNamespace(
            fetch_daily_transaction_snapshot=fake_fetch,
            persist_producer_health_summary=fake_health,
            run_observer=unexpected_observer,
        ),
    )

    summary = _persist_usaspending_obligation_observer("20260730")

    assert fetch_calls == ["20260730"]
    assert [call["run_date"] for call in health_calls] == ["2026-07-29"]
    assert summary["status"] == "pending"
    assert summary["run_date"] == "2026-07-29"
    assert summary["trade_enabled"] is False


def test_usaspending_daily_wiring_consumes_prior_success_then_persists_current_health(
    monkeypatch, tmp_path
):
    prior_snapshot = tmp_path / "transaction_snapshot_20260729.zip"
    prior_snapshot.write_bytes(b"PK-prior")
    persisted_daily_snapshot = tmp_path / "daily_non_ohlcv_snapshot_20260730.json"
    producer_results = [
        {
            "status": "ok",
            "producer_mode": "official_daily_transaction_download",
            "source_mode": "official_producer",
            "run_date": "2026-07-29",
            "snapshot_path": str(prior_snapshot),
            "retrieved_at_utc": "2026-07-30T15:00:00Z",
            "resumed_pending_job": True,
            "pending_job_validation_status": "validated",
        },
        {
            "status": "pending",
            "producer_mode": "official_daily_transaction_download",
            "source_mode": "official_producer",
            "run_date": "2026-07-30",
            "job_requested_at_utc": "2026-07-30T15:01:00Z",
            "resumed_pending_job": False,
            "pending_job_validation_status": "validated",
            "error": "USAspending status poll budget exhausted",
        },
    ]
    fetch_calls = []
    observer_calls = []
    health_calls = []

    def fake_fetch(run_date):
        fetch_calls.append(run_date)
        return producer_results[len(fetch_calls) - 1]

    def fake_observer(**kwargs):
        observer_calls.append(kwargs)
        return {
            "status": "ok",
            "rows_appended": 3,
            "new_forward_rows_appended": 3,
            "new_eligible_forward_rows_appended": 1,
        }

    def fake_health(**kwargs):
        health_calls.append(kwargs)
        producer = dict(kwargs["producer_result"])
        observer = dict(kwargs.get("observer_summary") or {})
        status = producer["status"]
        return {
            **producer,
            **observer,
            "status": status,
            "producer_status": status,
            "producer_health_status": status,
            "reason": None if status == "ok" else "producer_pending",
        }

    monkeypatch.delenv("GINGER_USASPENDING_TRANSACTION_SNAPSHOT", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "usaspending_obligation_observer",
        types.SimpleNamespace(
            fetch_daily_transaction_snapshot=fake_fetch,
            persist_producer_health_summary=fake_health,
            run_observer=fake_observer,
        ),
    )
    non_ohlcv_snapshot = {
        "status": "ok",
        "paths": {"summary": str(persisted_daily_snapshot)},
        "coverage_manifest": {},
    }

    summary = _persist_usaspending_obligation_observer(
        "20260730", non_ohlcv_snapshot
    )

    assert fetch_calls == ["20260730", "20260730"]
    assert observer_calls == [
        {
            "snapshot_path": str(prior_snapshot),
            "observed_at": "2026-07-30T15:00:00Z",
        }
    ]
    assert [call["run_date"] for call in health_calls] == [
        "2026-07-29",
        "2026-07-30",
    ]
    assert summary["status"] == "pending"
    assert summary["run_date"] == "2026-07-30"
    assert summary["recovered_prior_run_date"] == "2026-07-29"
    assert summary["recovered_prior_status"] == "ok"
    assert summary["recovered_prior_rows_appended"] == 3
    assert summary["daily_snapshot_health_persisted"] is True
    persisted = json.loads(persisted_daily_snapshot.read_text(encoding="utf-8"))
    coverage = persisted["coverage_manifest"]["usaspending_obligation_observer"]
    assert coverage["status"] == "pending"
    assert coverage["run_date"] == "2026-07-30"
    assert coverage["recovered_prior_run_date"] == "2026-07-29"
    assert coverage["daily_snapshot_health_persisted"] is True
    assert summary["trade_enabled"] is False


def test_usaspending_obligation_observer_fails_closed_when_override_is_missing(
    monkeypatch, tmp_path
):
    snapshot_path = tmp_path / "missing_usaspending_transactions.json"
    observer_calls = []
    health_calls = []

    def unexpected_run_observer(**kwargs):
        observer_calls.append(kwargs)

    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("configured local override must not call the producer")

    def fake_persist_health(**kwargs):
        health_calls.append(kwargs)
        producer = kwargs["producer_result"]
        return {
            **producer,
            "status": "unavailable",
            "producer_status": "unavailable",
            "snapshot_fresh": False,
        }

    monkeypatch.setenv(
        "GINGER_USASPENDING_TRANSACTION_SNAPSHOT",
        str(snapshot_path),
    )
    monkeypatch.setitem(
        sys.modules,
        "usaspending_obligation_observer",
        types.SimpleNamespace(
            fetch_daily_transaction_snapshot=unexpected_fetch,
            persist_producer_health_summary=fake_persist_health,
            run_observer=unexpected_run_observer,
        ),
    )

    summary = _persist_usaspending_obligation_observer("20260713")

    assert observer_calls == []
    assert len(health_calls) == 1
    assert summary["status"] == "unavailable"
    assert summary["reason"] == "transaction_snapshot_missing"
    assert summary["snapshot_path"] == str(snapshot_path)
    assert summary["snapshot_fresh"] is False
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False


def test_usaspending_obligation_observer_daily_wiring_is_fail_soft(
    monkeypatch, tmp_path
):
    snapshot_path = tmp_path / "usaspending_transactions.json"
    snapshot_path.write_text("{}", encoding="utf-8")

    def failing_run_observer(**kwargs):
        raise RuntimeError("USAspending observer unavailable")

    def fake_persist_health(**kwargs):
        return {
            **dict(kwargs["producer_result"]),
            "status": "unavailable",
            "producer_status": "unavailable",
            "error": kwargs.get("error"),
            "snapshot_fresh": False,
        }

    monkeypatch.setenv(
        "GINGER_USASPENDING_TRANSACTION_SNAPSHOT",
        str(snapshot_path),
    )
    monkeypatch.setitem(
        sys.modules,
        "usaspending_obligation_observer",
        types.SimpleNamespace(
            fetch_daily_transaction_snapshot=lambda *_args, **_kwargs: None,
            persist_producer_health_summary=fake_persist_health,
            run_observer=failing_run_observer,
        ),
    )

    summary = _persist_usaspending_obligation_observer("20260713")

    assert summary["status"] == "unavailable"
    assert "USAspending observer unavailable" in summary["error"]
    assert summary["snapshot_path"] == str(snapshot_path)
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False
    assert summary["alters_orders"] is False
    assert summary["alters_ranking"] is False
    assert summary["alters_sizing"] is False
    assert summary["alters_exits"] is False


def test_usaspending_obligation_observer_is_wired_in_both_daily_paths():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    call_expressions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None)
        == "_persist_usaspending_obligation_observer"
    ]

    assert len(call_expressions) == 2
    assert all(
        isinstance(expression.value, ast.Call)
        and len(expression.value.args) == 2
        and isinstance(expression.value.args[0], ast.Name)
        and expression.value.args[0].id == "today"
        and isinstance(expression.value.args[1], ast.Name)
        and expression.value.args[1].id == "non_ohlcv_snapshot"
        for expression in call_expressions
    )


def test_entity_theme_news_outcome_daily_wiring(monkeypatch):
    calls = {"persist": 0}

    def fake_persist_entity_theme_news_outcome_ledger(today):
        calls["persist"] += 1
        assert today == "20260703"
        return {
            "status": "ok",
            "daily_item_file_count": 2,
            "candidate_outcome_row_count": 8,
            "settled_count": 3,
            "unsettled_count": 5,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
        }

    monkeypatch.setitem(
        sys.modules,
        "entity_theme_news_observer",
        types.SimpleNamespace(
            persist_entity_theme_news_outcome_ledger=(
                fake_persist_entity_theme_news_outcome_ledger
            )
        ),
    )

    summary = _persist_entity_theme_news_outcomes("20260703")

    assert calls == {"persist": 1}
    assert summary["status"] == "ok"
    assert summary["daily_item_file_count"] == 2
    assert summary["candidate_outcome_row_count"] == 8
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False


def test_entity_theme_news_outcome_daily_wiring_fail_soft(monkeypatch):
    def failing_persist_entity_theme_news_outcome_ledger(today):
        raise RuntimeError("entity theme outcomes unavailable")

    monkeypatch.setitem(
        sys.modules,
        "entity_theme_news_observer",
        types.SimpleNamespace(
            persist_entity_theme_news_outcome_ledger=(
                failing_persist_entity_theme_news_outcome_ledger
            )
        ),
    )

    summary = _persist_entity_theme_news_outcomes("20260703")

    assert summary["status"] == "unavailable"
    assert "entity theme outcomes unavailable" in summary["error"]
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False


def test_prediction_market_event_observer_daily_wiring(monkeypatch):
    calls = {"persist": 0}

    def fake_persist_prediction_market_event_observer(today):
        calls["persist"] += 1
        assert today == "20260703"
        return {
            "status": "ok",
            "source_count": 6,
            "raw_item_count": 6,
            "unique_item_count": 6,
            "source_error_count": 0,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
        }

    monkeypatch.setitem(
        sys.modules,
        "prediction_market_event_observer",
        types.SimpleNamespace(
            persist_prediction_market_event_observer=(
                fake_persist_prediction_market_event_observer
            )
        ),
    )

    summary = _persist_prediction_market_event_observer("20260703")

    assert calls == {"persist": 1}
    assert summary["status"] == "ok"
    assert summary["source_count"] == 6
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False


def test_prediction_market_event_observer_daily_wiring_fail_soft(monkeypatch):
    def failing_persist_prediction_market_event_observer(today):
        raise RuntimeError("prediction market unavailable")

    monkeypatch.setitem(
        sys.modules,
        "prediction_market_event_observer",
        types.SimpleNamespace(
            persist_prediction_market_event_observer=(
                failing_persist_prediction_market_event_observer
            )
        ),
    )

    summary = _persist_prediction_market_event_observer("20260703")

    assert summary["status"] == "unavailable"
    assert "prediction market unavailable" in summary["error"]
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False


def test_prediction_market_event_outcome_daily_wiring(monkeypatch):
    calls = {"persist": 0}

    def fake_persist_prediction_market_event_outcome_ledger(today):
        calls["persist"] += 1
        assert today == "20260703"
        return {
            "status": "ok",
            "daily_item_file_count": 2,
            "candidate_outcome_row_count": 8,
            "settled_count": 3,
            "unsettled_count": 5,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
        }

    monkeypatch.setitem(
        sys.modules,
        "prediction_market_event_observer",
        types.SimpleNamespace(
            persist_prediction_market_event_outcome_ledger=(
                fake_persist_prediction_market_event_outcome_ledger
            )
        ),
    )

    summary = _persist_prediction_market_event_outcomes("20260703")

    assert calls == {"persist": 1}
    assert summary["status"] == "ok"
    assert summary["daily_item_file_count"] == 2
    assert summary["candidate_outcome_row_count"] == 8
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False


def test_prediction_market_event_outcome_daily_wiring_fail_soft(monkeypatch):
    def failing_persist_prediction_market_event_outcome_ledger(today):
        raise RuntimeError("prediction market outcomes unavailable")

    monkeypatch.setitem(
        sys.modules,
        "prediction_market_event_observer",
        types.SimpleNamespace(
            persist_prediction_market_event_outcome_ledger=(
                failing_persist_prediction_market_event_outcome_ledger
            )
        ),
    )

    summary = _persist_prediction_market_event_outcomes("20260703")

    assert summary["status"] == "unavailable"
    assert "prediction market outcomes unavailable" in summary["error"]
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False


def test_moomoo_capital_flow_paper_sleeve_daily_wiring_uses_shared_helper():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    expected_imports = {
        "empty_moomoo_capital_flow_paper_sleeve_snapshot",
        "prep_and_build_moomoo_capital_flow_paper_sleeve_snapshot",
    }
    imported_names = set()
    referenced_names = set()
    helper_calls = []
    quant_artifact_keys = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "moomoo_capital_flow_paper_sleeve":
            imported_names.update(alias.name for alias in node.names)
        if isinstance(node, ast.Name):
            referenced_names.add(node.id)
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None)
            == "prep_and_build_moomoo_capital_flow_paper_sleeve_snapshot"
        ):
            helper_calls.append(node)
        if isinstance(node, ast.Dict):
            quant_artifact_keys.extend(
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )

    assert expected_imports <= imported_names
    assert "empty_moomoo_capital_flow_paper_sleeve_snapshot" in referenced_names
    assert helper_calls

    helper_kwargs = {keyword.arg for keyword in helper_calls[0].keywords}
    assert {
        "as_of",
        "ohlcv_dict",
        "spy_ohlcv",
        "same_day_core_tickers",
        "open_prices",
        "current_prices",
    } <= helper_kwargs
    assert "moomoo_capital_flow_paper_sleeve" in quant_artifact_keys


def test_moomoo_capital_flow_paper_sleeve_not_added_to_prompt_trend_signals():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    prompt_facing_assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if getattr(target.value, "id", None) != "trend_signals_dict":
                continue
            slice_node = target.slice
            if (
                isinstance(slice_node, ast.Constant)
                and slice_node.value == "moomoo_capital_flow_paper_sleeve"
            ):
                prompt_facing_assignments.append(node)

    assert prompt_facing_assignments == []

def test_finra_ats_share_paper_sleeve_daily_wiring_uses_shared_helper():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    expected_imports = {
        "empty_finra_ats_share_paper_sleeve_snapshot",
        "prep_and_build_finra_ats_share_paper_sleeve_snapshot",
    }
    imported_names = set()
    referenced_names = set()
    helper_calls = []
    quant_artifact_keys = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "finra_ats_share_paper_sleeve":
            imported_names.update(alias.name for alias in node.names)
        if isinstance(node, ast.Name):
            referenced_names.add(node.id)
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None)
            == "prep_and_build_finra_ats_share_paper_sleeve_snapshot"
        ):
            helper_calls.append(node)
        if isinstance(node, ast.Dict):
            quant_artifact_keys.extend(
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )

    assert expected_imports <= imported_names
    assert "empty_finra_ats_share_paper_sleeve_snapshot" in referenced_names
    assert helper_calls

    helper_kwargs = {keyword.arg for keyword in helper_calls[0].keywords}
    assert {
        "as_of",
        "ohlcv_dict",
        "spy_ohlcv",
        "same_day_core_tickers",
        "open_prices",
        "current_prices",
    } <= helper_kwargs
    assert "finra_ats_share_paper_sleeve" in quant_artifact_keys


def test_finra_ats_share_paper_sleeve_not_added_to_prompt_trend_signals():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    prompt_facing_assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if getattr(target.value, "id", None) != "trend_signals_dict":
                continue
            slice_node = target.slice
            if (
                isinstance(slice_node, ast.Constant)
                and slice_node.value == "finra_ats_share_paper_sleeve"
            ):
                prompt_facing_assignments.append(node)

    assert prompt_facing_assignments == []


def test_finra_otc_internalization_paper_sleeve_daily_wiring_uses_shared_helper():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    expected_imports = {
        "empty_finra_otc_internalization_paper_sleeve_snapshot",
        "prep_and_build_finra_otc_internalization_paper_sleeve_snapshot",
    }
    imported_names = set()
    referenced_names = set()
    helper_calls = []
    quant_artifact_keys = []

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "finra_otc_internalization_paper_sleeve"
        ):
            imported_names.update(alias.name for alias in node.names)
        if isinstance(node, ast.Name):
            referenced_names.add(node.id)
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None)
            == "prep_and_build_finra_otc_internalization_paper_sleeve_snapshot"
        ):
            helper_calls.append(node)
        if isinstance(node, ast.Dict):
            quant_artifact_keys.extend(
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )

    assert expected_imports <= imported_names
    assert "empty_finra_otc_internalization_paper_sleeve_snapshot" in referenced_names
    assert helper_calls

    helper_kwargs = {keyword.arg for keyword in helper_calls[0].keywords}
    assert {
        "as_of",
        "ohlcv_dict",
        "spy_ohlcv",
        "same_day_core_tickers",
        "open_prices",
        "current_prices",
    } <= helper_kwargs
    assert "finra_otc_internalization_paper_sleeve" in quant_artifact_keys


def test_finra_otc_internalization_paper_sleeve_not_added_to_prompt_trend_signals():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    prompt_facing_assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if getattr(target.value, "id", None) != "trend_signals_dict":
                continue
            slice_node = target.slice
            if (
                isinstance(slice_node, ast.Constant)
                and slice_node.value == "finra_otc_internalization_paper_sleeve"
            ):
                prompt_facing_assignments.append(node)

    assert prompt_facing_assignments == []


def test_sec_item101_contract_relation_paper_sleeve_daily_wiring_uses_shared_helper():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    expected_imports = {
        "empty_sec_item101_contract_relation_paper_sleeve_snapshot",
        "prep_and_build_sec_item101_contract_relation_paper_sleeve_snapshot",
    }
    imported_names = set()
    referenced_names = set()
    helper_calls = []
    quant_artifact_keys = []

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "sec_item101_contract_relation_paper_sleeve"
        ):
            imported_names.update(alias.name for alias in node.names)
        if isinstance(node, ast.Name):
            referenced_names.add(node.id)
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None)
            == "prep_and_build_sec_item101_contract_relation_paper_sleeve_snapshot"
        ):
            helper_calls.append(node)
        if isinstance(node, ast.Dict):
            quant_artifact_keys.extend(
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )

    assert expected_imports <= imported_names
    assert "empty_sec_item101_contract_relation_paper_sleeve_snapshot" in referenced_names
    assert helper_calls

    helper_kwargs = {keyword.arg for keyword in helper_calls[0].keywords}
    assert {
        "as_of",
        "ohlcv_dict",
        "spy_ohlcv",
        "open_prices",
        "current_prices",
    } <= helper_kwargs
    assert "sec_item101_contract_relation_paper_sleeve" in quant_artifact_keys


def test_sec_item101_contract_relation_paper_sleeve_not_added_to_prompt_trend_signals():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    prompt_facing_assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if getattr(target.value, "id", None) != "trend_signals_dict":
                continue
            slice_node = target.slice
            if (
                isinstance(slice_node, ast.Constant)
                and slice_node.value == "sec_item101_contract_relation_paper_sleeve"
            ):
                prompt_facing_assignments.append(node)

    assert prompt_facing_assignments == []


def test_options_quality_gate_refreshed_before_flow_put_sleeve_build():
    """exp-20260725-004: the flow-put sleeve reads the options collection
    quality gate at build time, so the pre-sleeve gate refresh must run
    before the sleeve build and the full ledger refresh must stay after."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    pre_refresh_linenos = []
    sleeve_build_linenos = []
    post_ledger_linenos = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_id = getattr(node.func, "id", None)
        if func_id == "_refresh_options_quality_gate_before_sleeves":
            pre_refresh_linenos.append(node.lineno)
        if func_id == "prep_and_build_core_drawdown_flow_put_snapshot":
            sleeve_build_linenos.append(node.lineno)
        if func_id == "_refresh_options_forward_ledger_after_quant_signals":
            post_ledger_linenos.append(node.lineno)

    assert pre_refresh_linenos, "pre-sleeve quality gate refresh missing from main"
    assert sleeve_build_linenos, "flow-put sleeve build missing from main"
    assert post_ledger_linenos, "post-quant options forward ledger refresh missing from main"
    assert min(pre_refresh_linenos) < min(sleeve_build_linenos)
    assert min(sleeve_build_linenos) < min(post_ledger_linenos)


def test_options_forward_settlement_reads_canonical_hot_overlay(tmp_path):
    """exp-20260727-001: recent settlement bars live in the sibling hot DB.

    The options ledger must consume the canonical overlay, preserve cold
    history, and prefer corrected hot rows on duplicate ticker-dates.
    """
    import importlib.util

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_options_forward_ledger.py"
    spec = importlib.util.spec_from_file_location(
        "run_options_forward_ledger_for_hot_overlay_test", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cold_path = tmp_path / "warehouse_main.sqlite"
    hot_path = tmp_path / "warehouse_main_hot.sqlite"
    schema = """
        CREATE TABLE ohlcv (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            source TEXT,
            updated_at TEXT,
            PRIMARY KEY (ticker, date)
        )
    """
    with sqlite3.connect(cold_path) as conn:
        conn.execute(schema)
        conn.executemany(
            "INSERT INTO ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("AAA", "2026-06-15", 99.0, 101.0, 98.0, 100.0, 1000.0, "cold", "2026-06-16T00:00:00Z"),
                ("AAA", "2026-07-23", 199.0, 201.0, 198.0, 200.0, 2000.0, "cold", "2026-07-24T00:00:00Z"),
            ],
        )
    with sqlite3.connect(hot_path) as conn:
        conn.execute(schema)
        conn.executemany(
            "INSERT INTO ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("AAA", "2026-07-23", 219.0, 223.0, 218.0, 222.0, 2200.0, "hot", "2026-07-24T01:00:00Z"),
                ("AAA", "2026-07-24", 223.0, 226.0, 222.0, 225.0, 2300.0, "hot", "2026-07-25T01:00:00Z"),
            ],
        )

    diagnostics = {}
    rows = module._load_ohlcv_warehouse(
        cold_path,
        tickers={"AAA"},
        diagnostics=diagnostics,
    )["AAA"]
    rows_by_date = {row["date"]: row for row in rows}

    assert set(rows_by_date) == {"2026-06-15", "2026-07-23", "2026-07-24"}
    assert rows_by_date["2026-07-23"]["close"] == 222.0
    assert diagnostics["hot_exists"] is True
    assert diagnostics["hot_attached"] is True
    assert diagnostics["hot_error"] is None
    assert module.forward_stats(rows, "2026-07-24")["outcome_status"] != "signal_date_missing_in_ohlcv"


def test_refresh_collection_quality_gate_writes_current_quote_date(tmp_path, monkeypatch):
    """exp-20260725-004: the quality-gate-only refresh must materialize a
    scoring_allowed row for a healthy current quote date and keep genuinely
    bad dates fail-closed (quarantined)."""
    import importlib.util
    import json as _json

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_options_forward_ledger.py"
    spec = importlib.util.spec_from_file_location(
        "run_options_forward_ledger_for_quality_gate_test", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    chain_dir = tmp_path / "chains"
    chain_dir.mkdir()
    healthy_date = "2026-07-24"
    healthy_rows = []
    for ticker_index in range(12):
        ticker = f"TK{ticker_index:02d}"
        for row_index in range(12):
            healthy_rows.append(
                {
                    "ticker": ticker,
                    "quote_date": healthy_date,
                    "bid": 1.0,
                    "ask": 1.2,
                    "mid": 1.1,
                    "volume": 25,
                    "open_interest": 500,
                    "delta": 0.4,
                    "implied_vol": 0.3,
                    "option_liquidity_pass": True,
                    "option_liquidity_score": "pass",
                    "usable_trade_date": "2026-07-27",
                    "pit_safe": True,
                    "strike": 100.0 + row_index,
                    "call_put": "put" if row_index % 2 else "call",
                    "expiration": "2026-08-21",
                }
            )
    healthy_path = chain_dir / "options_onclickmedia_chain_20260724.jsonl"
    healthy_path.write_text(
        "\n".join(_json.dumps(row) for row in healthy_rows) + "\n", encoding="utf-8"
    )

    sparse_date = "2026-07-23"
    sparse_rows = [
        {
            "ticker": "TK00",
            "quote_date": sparse_date,
            "bid": 0.0,
            "ask": 0.0,
            "mid": 0.0,
            "volume": 0,
            "open_interest": 0,
            "delta": 0.0,
            "implied_vol": 0.0,
            "option_liquidity_pass": False,
            "option_liquidity_score": "fail",
        }
    ]
    sparse_path = chain_dir / "options_onclickmedia_chain_20260723.jsonl"
    sparse_path.write_text(
        "\n".join(_json.dumps(row) for row in sparse_rows) + "\n", encoding="utf-8"
    )

    output_dir = tmp_path / "options_forward"
    summary = module.refresh_collection_quality_gate(
        chain_dir=chain_dir,
        output_dir=output_dir,
    )

    gate_path = output_dir / "options_collection_quality_gate.json"
    assert gate_path.exists()
    payload = _json.loads(gate_path.read_text(encoding="utf-8"))
    healthy_row = payload["by_quote_date"][healthy_date]
    assert healthy_row["scoring_allowed"] is True
    assert healthy_row["status"] == "usable_for_shadow"
    sparse_row = payload["by_quote_date"][sparse_date]
    assert sparse_row["scoring_allowed"] is False
    assert sparse_row["status"] == "quarantined"
    assert healthy_date in summary["usable_quote_dates"]
    assert sparse_date in summary["quarantined_quote_dates"]


def test_massive_dividend_restart_forward_observer_is_wired_in_both_daily_paths():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    call_expressions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None)
        == "_persist_massive_dividend_restart_forward_observer"
    ]

    assert len(call_expressions) == 2
    assert all(
        isinstance(expression.value, ast.Call)
        and len(expression.value.args) == 2
        and isinstance(expression.value.args[0], ast.Name)
        and expression.value.args[0].id == "today"
        and isinstance(expression.value.args[1], ast.Name)
        and expression.value.args[1].id == "non_ohlcv_snapshot"
        for expression in call_expressions
    )


def test_massive_dividend_restart_forward_observer_reports_coverage(monkeypatch):
    observer_calls = []

    def fake_persist(today):
        observer_calls.append(today)
        return {
            "status": "ok",
            "fetched_at": "2026-08-02T21:00:00Z",
            "content_identity": "a" * 64,
            "page_count": 3,
            "positive_usd_row_count": 1200,
            "max_declaration_date": "2026-07-31",
            "new_candidate_count": 1,
            "candidate_count_total": 4,
            "eligible_candidate_count": 2,
            "pending_gate_count": 1,
            "consecutive_unchanged_content_runs": 0,
            "expected_cadence": (
                "at_least_one_coverage_row_per_trading_day_zero_candidates_normal"
            ),
        }

    monkeypatch.setitem(
        sys.modules,
        "massive_dividend_restart_forward_observer",
        types.SimpleNamespace(
            persist_massive_dividend_restart_forward_observer=fake_persist
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_massive_dividend_restart_forward_observer(
        "20260802", non_ohlcv_snapshot
    )

    assert observer_calls == ["20260802"]
    assert summary["status"] == "ok"
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False
    assert summary["alters_orders"] is False
    coverage = non_ohlcv_snapshot["coverage_manifest"][
        "massive_dividend_restart_forward_observer"
    ]
    assert coverage["status"] == "ok"
    assert coverage["max_declaration_date"] == "2026-07-31"
    assert coverage["new_candidate_count"] == 1
    assert coverage["pending_gate_count"] == 1
    assert coverage["expected_cadence"].startswith("at_least_one_coverage_row")


def test_massive_dividend_restart_forward_observer_nonok_status_binds_alert(
    monkeypatch,
):
    def fake_persist(today):
        return {
            "status": "stale_input",
            "alert": True,
            "reason": "content_identity_unchanged_for_consecutive_runs",
            "consecutive_unchanged_content_runs": 3,
        }

    monkeypatch.setitem(
        sys.modules,
        "massive_dividend_restart_forward_observer",
        types.SimpleNamespace(
            persist_massive_dividend_restart_forward_observer=fake_persist
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_massive_dividend_restart_forward_observer(
        "20260802", non_ohlcv_snapshot
    )

    assert summary["status"] == "stale_input"
    coverage = non_ohlcv_snapshot["coverage_manifest"][
        "massive_dividend_restart_forward_observer"
    ]
    assert coverage["status"] == "stale_input"
    assert coverage["alert"] is True
    assert coverage["reason"] == "content_identity_unchanged_for_consecutive_runs"


def test_massive_dividend_restart_forward_observer_daily_wiring_fail_soft(
    monkeypatch,
):
    def failing_persist(today):
        raise RuntimeError("simulated observer crash")

    monkeypatch.setitem(
        sys.modules,
        "massive_dividend_restart_forward_observer",
        types.SimpleNamespace(
            persist_massive_dividend_restart_forward_observer=failing_persist
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_massive_dividend_restart_forward_observer(
        "20260802", non_ohlcv_snapshot
    )

    assert summary["status"] == "error"
    assert summary["reason"] == "observer_exception"
    assert summary["trade_enabled"] is False
    coverage = non_ohlcv_snapshot["coverage_manifest"][
        "massive_dividend_restart_forward_observer"
    ]
    assert coverage["status"] == "error"
    assert coverage["alert"] is True
    assert "simulated observer crash" in coverage["error"]


def test_massive_ohlcv_grouped_catchup_is_wired_before_observer():
    # exp-20260805-004: the settlement chain starved for 12 days because
    # nothing advanced daily_bars in the daily run. The bounded catch-up must
    # run ahead of the observer/settlement pair in both daily paths.
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    ordered_names = [
        node.value.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None)
        in (
            "_run_massive_ohlcv_grouped_catchup",
            "_persist_massive_dividend_restart_forward_observer",
            "_persist_massive_dividend_restart_forward_settlement",
        )
    ]
    assert ordered_names == [
        "_run_massive_ohlcv_grouped_catchup",
        "_persist_massive_dividend_restart_forward_observer",
        "_persist_massive_dividend_restart_forward_settlement",
        "_run_massive_ohlcv_grouped_catchup",
        "_persist_massive_dividend_restart_forward_observer",
        "_persist_massive_dividend_restart_forward_settlement",
    ]


def test_massive_ohlcv_grouped_catchup_binds_coverage_and_fail_soft(monkeypatch):
    def fake_catchup():
        return {
            "status": "complete",
            "alert": False,
            "latest_completed_session": "2026-08-04",
            "bars_max_trade_date_before": "2026-07-24",
            "bars_max_trade_date_after": "2026-08-04",
            "dates_fetched": 6,
            "dates_skipped": 1,
            "rows_fetched": 74634,
            "remaining_missing_weekdays": 0,
        }

    monkeypatch.setitem(
        sys.modules,
        "massive_ohlcv_backfill",
        types.SimpleNamespace(run_incremental_grouped_catchup=fake_catchup),
    )
    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _run_massive_ohlcv_grouped_catchup("20260805", non_ohlcv_snapshot)
    assert summary["status"] == "complete"
    coverage = non_ohlcv_snapshot["coverage_manifest"][
        "massive_ohlcv_grouped_catchup"
    ]
    assert coverage["bars_max_trade_date_after"] == "2026-08-04"
    assert coverage["dates_fetched"] == 6

    def raising_catchup():
        raise RuntimeError("boom")

    monkeypatch.setitem(
        sys.modules,
        "massive_ohlcv_backfill",
        types.SimpleNamespace(run_incremental_grouped_catchup=raising_catchup),
    )
    snapshot_two = {"coverage_manifest": {}}
    failed = _run_massive_ohlcv_grouped_catchup("20260805", snapshot_two)
    assert failed["status"] == "error"
    assert failed["alert"] is True
    fail_coverage = snapshot_two["coverage_manifest"][
        "massive_ohlcv_grouped_catchup"
    ]
    assert fail_coverage["status"] == "error"
    assert fail_coverage["alert"] is True


def test_massive_dividend_restart_forward_settlement_is_wired_after_observer():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    settlement_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None)
        == "_persist_massive_dividend_restart_forward_settlement"
    ]

    assert len(settlement_calls) == 2
    assert all(
        len(expression.value.args) == 2
        and isinstance(expression.value.args[0], ast.Name)
        and expression.value.args[0].id == "today"
        and isinstance(expression.value.args[1], ast.Name)
        and expression.value.args[1].id == "non_ohlcv_snapshot"
        for expression in settlement_calls
    )

    # Producer-before-consumer: in the flat statement order of main(), every
    # settlement call must appear after an observer call.
    ordered_names = [
        node.value.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None)
        in (
            "_persist_massive_dividend_restart_forward_observer",
            "_persist_massive_dividend_restart_forward_settlement",
        )
    ]
    assert ordered_names == [
        "_persist_massive_dividend_restart_forward_observer",
        "_persist_massive_dividend_restart_forward_settlement",
        "_persist_massive_dividend_restart_forward_observer",
        "_persist_massive_dividend_restart_forward_settlement",
    ]


def test_massive_dividend_restart_forward_settlement_reports_coverage(monkeypatch):
    settlement_calls = []

    def fake_persist(today):
        settlement_calls.append(today)
        return {
            "status": "ok",
            "warehouse_max_trade_date": "2026-07-24",
            "decision_count_total": 3,
            "settled_decision_count": 1,
            "settled_restart_decision_count": 1,
            "voided_decision_count": 0,
            "pending_settlement_count": 2,
            "pending_declaration_date_count": 4,
            "late_discovery_excluded_count": 0,
            "new_event_count": 2,
            "reopen_progress": {"required": 30, "settled_restart_decisions": 1},
        }

    monkeypatch.setitem(
        sys.modules,
        "massive_dividend_restart_forward_settlement",
        types.SimpleNamespace(
            persist_massive_dividend_restart_forward_settlement=fake_persist
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_massive_dividend_restart_forward_settlement(
        "20260803", non_ohlcv_snapshot
    )

    assert settlement_calls == ["20260803"]
    assert summary["status"] == "ok"
    assert summary["trade_enabled"] is False
    assert summary["strategy_behavior_changed"] is False
    assert summary["alters_orders"] is False
    coverage = non_ohlcv_snapshot["coverage_manifest"][
        "massive_dividend_restart_forward_settlement"
    ]
    assert coverage["status"] == "ok"
    assert coverage["warehouse_max_trade_date"] == "2026-07-24"
    assert coverage["settled_restart_decision_count"] == 1
    assert coverage["pending_settlement_count"] == 2
    assert coverage["reopen_progress"]["required"] == 30


def test_massive_dividend_restart_forward_settlement_nonok_binds_alert(
    monkeypatch,
):
    def fake_persist(today):
        return {
            "status": "blocked_missing_bars_database",
            "alert": True,
            "reason": "bars_database_not_found",
        }

    monkeypatch.setitem(
        sys.modules,
        "massive_dividend_restart_forward_settlement",
        types.SimpleNamespace(
            persist_massive_dividend_restart_forward_settlement=fake_persist
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_massive_dividend_restart_forward_settlement(
        "20260803", non_ohlcv_snapshot
    )

    assert summary["status"] == "blocked_missing_bars_database"
    coverage = non_ohlcv_snapshot["coverage_manifest"][
        "massive_dividend_restart_forward_settlement"
    ]
    assert coverage["status"] == "blocked_missing_bars_database"
    assert coverage["alert"] is True
    assert coverage["reason"] == "bars_database_not_found"


def test_massive_dividend_restart_forward_settlement_daily_wiring_fail_soft(
    monkeypatch,
):
    def failing_persist(today):
        raise RuntimeError("simulated settlement crash")

    monkeypatch.setitem(
        sys.modules,
        "massive_dividend_restart_forward_settlement",
        types.SimpleNamespace(
            persist_massive_dividend_restart_forward_settlement=failing_persist
        ),
    )

    non_ohlcv_snapshot = {"coverage_manifest": {}}
    summary = _persist_massive_dividend_restart_forward_settlement(
        "20260803", non_ohlcv_snapshot
    )

    assert summary["status"] == "error"
    assert summary["reason"] == "settlement_exception"
    assert summary["trade_enabled"] is False
    coverage = non_ohlcv_snapshot["coverage_manifest"][
        "massive_dividend_restart_forward_settlement"
    ]
    assert coverage["status"] == "error"
    assert coverage["alert"] is True
    assert "simulated settlement crash" in coverage["error"]
