import ast
from datetime import date
import inspect
from pathlib import Path
import sys
import textwrap
import types


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import run as run_module  # noqa: E402
from fundamental_growth_rs_paper_sleeve import (  # noqa: E402
    prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot,
)
from run import (  # noqa: E402
    _core_slot_ticker_set,
    _persist_daily_structured_news_observation,
    _persist_entity_theme_news_observer,
    _persist_entity_theme_news_outcomes,
    _persist_prediction_market_event_observer,
    _persist_prediction_market_event_outcomes,
    _persist_sec_corporate_event_stream,
    _refresh_estimate_revision_ledger_after_quant_signals,
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
