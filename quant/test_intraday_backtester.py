import json
from pathlib import Path
import sys
import types

import intraday_backtester as intraday_backtester_module
from intraday_backtester import (
    HORIZONS,
    build_intraday_outcomes,
    build_scorecard,
    fetch_opend_history,
    load_finalized_decisions,
    migrate_intraday_outcomes_to_current_rule,
    run_intraday_backtest,
)


def _bar(day, hhmm, price, *, high=None, low=None):
    return {
        "time_key": f"{day} {hhmm}:00",
        "open": price,
        "high": high if high is not None else price + 0.5,
        "low": low if low is not None else price - 0.5,
        "close": price,
    }


def _bars(prices=None):
    prices = prices or {
        "10:05": 101.0,
        "10:10": 102.0,
        "10:15": 103.0,
        "11:05": 106.0,
        "15:55": 108.0,
    }
    rows = [_bar("2026-07-10", hhmm, price) for hhmm, price in prices.items()]
    rows.extend([
        _bar("2026-07-13", "09:30", 109.0),
        _bar("2026-07-13", "15:55", 110.0),
        _bar("2026-07-14", "15:55", 111.0),
        _bar("2026-07-15", "15:55", 112.0),
    ])
    return rows


def _decision(action="ADD_SMALL", default="WAIT"):
    return {
        "observation_id": "obs-1",
        "source_decision_file": "data/daily/intraday/decisions/example.json",
        "ticker": "NVDA",
        "decision_date": "2026-07-10",
        "decision_timestamp": "2026-07-10 10:00:00",
        "timestamp_et": "2026-07-10 10:00 ET",
        "primary_ticker_day_decision": True,
        "market_phase": "RTH",
        "action_label": action,
        "machine_default_action": default,
        "underlying": None,
        "sector_proxy": "SMH",
        "market_proxy": "QQQ",
        "confidence": 0.7,
        "entry_condition": {"confirmation_level": 102.0},
        "invalidation_level": 90.0,
        "paper_execution": {
            "position_market_value_at_decision": 10_000.0,
            "max_add_fraction_existing_position": 0.20,
            "counterfactual_add_fraction_existing_position": 0.20,
            "reduce_fraction_existing_position": 0.25,
            "one_way_cost_bps": 5.0,
            "round_trip_cost_bps": 10.0,
        },
    }


def _all_bars(ticker_rows):
    return {
        "NVDA": ticker_rows,
        "SMH": _bars(),
        "QQQ": _bars(),
    }


def test_opend_fetch_redirects_sdk_import_log_and_restores_environment(monkeypatch):
    events = []

    def redirect():
        events.append("redirect")
        return "system-appdata"

    def restore(previous):
        events.append(("restore", previous))

    class FakeContext:
        def __init__(self, *, host, port):
            events.append(("connect", host, port))

        def close(self):
            events.append("close")

    fake_moomoo = types.ModuleType("moomoo")
    fake_moomoo.AuType = types.SimpleNamespace(QFQ="QFQ")
    fake_moomoo.KLType = types.SimpleNamespace(K_5M="K_5M")
    fake_moomoo.Session = types.SimpleNamespace(RTH="RTH")
    fake_moomoo.OpenQuoteContext = FakeContext
    monkeypatch.setitem(sys.modules, "moomoo", fake_moomoo)
    monkeypatch.setattr(
        intraday_backtester_module,
        "_redirect_moomoo_sdk_appdata",
        redirect,
    )
    monkeypatch.setattr(
        intraday_backtester_module,
        "_restore_moomoo_sdk_appdata",
        restore,
    )
    monkeypatch.setattr(
        intraday_backtester_module,
        "_history_pages",
        lambda *args, **kwargs: ([{
            "time_key": "2026-07-10 09:30:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
        }], None),
    )

    bars, source = fetch_opend_history(
        ["SPY"],
        start_date="2026-07-10",
        end_date="2026-07-10",
    )

    assert source["status"] == "ok"
    assert source["returned_bars"] == 1
    assert len(bars["SPY"]) == 1
    assert events[:3] == [
        "redirect",
        ("restore", "system-appdata"),
        ("connect", "127.0.0.1", 11111),
    ]
    assert events[-1] == "close"


def test_add_small_settles_all_horizons_and_semantic_lift():
    outcomes = build_intraday_outcomes(
        [_decision()],
        _all_bars(_bars()),
        as_of_date="2026-07-15",
    )
    assert [row["horizon"] for row in outcomes] == list(HORIZONS)
    assert {row["status"] for row in outcomes} == {"closed"}
    next_close = next(row for row in outcomes if row["horizon"] == "next_close")
    assert next_close["execution_time"] == "2026-07-10 10:05:00"
    assert next_close["final_result"]["paper_notional_usd"] == 2000.0
    assert next_close["incremental_pnl_vs_no_adjustment_usd"] > 0
    assert next_close["incremental_return_on_position_bps"] > 0
    assert (
        next_close["semantic_lift_vs_machine_default_usd"]
        == next_close["incremental_pnl_vs_no_adjustment_usd"]
    )


def test_reduce_risk_has_positive_avoided_loss_when_price_falls():
    falling = _bars({
        "10:05": 100.0,
        "10:10": 99.0,
        "10:15": 98.0,
        "11:05": 96.0,
        "15:55": 95.0,
    })
    falling[-3:] = [
        _bar("2026-07-13", "15:55", 90.0),
        _bar("2026-07-14", "15:55", 89.0),
        _bar("2026-07-15", "15:55", 88.0),
    ]
    outcomes = build_intraday_outcomes(
        [_decision("REDUCE_RISK", "REDUCE_RISK")],
        _all_bars(falling),
        as_of_date="2026-07-15",
    )
    rth = next(row for row in outcomes if row["horizon"] == "rth_close")
    assert rth["final_result"]["paper_notional_usd"] == 2500.0
    assert rth["final_result"]["paper_pnl_usd"] > 0
    assert rth["semantic_lift_vs_machine_default_usd"] == 0.0


def test_wait_scores_against_always_add_and_tracks_trigger():
    falling = [
        _bar("2026-07-10", "10:05", 101.0),
        _bar("2026-07-10", "10:10", 102.5),
        _bar("2026-07-10", "10:15", 102.0),
        _bar("2026-07-10", "11:05", 98.0),
        _bar("2026-07-10", "15:55", 95.0),
        _bar("2026-07-13", "15:55", 94.0),
        _bar("2026-07-14", "15:55", 93.0),
        _bar("2026-07-15", "15:55", 92.0),
    ]
    outcomes = build_intraday_outcomes(
        [_decision("WAIT", "WAIT")],
        _all_bars(falling),
        as_of_date="2026-07-15",
    )
    rth = next(row for row in outcomes if row["horizon"] == "rth_close")
    assert rth["incremental_pnl_vs_no_adjustment_usd"] == 0.0
    assert rth["always_add_result"]["paper_pnl_usd"] < 0
    assert rth["final_vs_always_add_usd"] > 0
    assert rth["wait_trigger_result"]["status"] == "closed"
    assert rth["wait_trigger_result"]["entry_time"] == "2026-07-10 10:15:00"


def test_add_invalidation_stop_precedes_horizon():
    rows = [
        _bar("2026-07-10", "10:05", 101.0, low=100.5),
        _bar("2026-07-10", "10:10", 99.0, low=89.0),
        _bar("2026-07-10", "11:05", 105.0),
        _bar("2026-07-10", "15:55", 108.0),
    ]
    outcomes = build_intraday_outcomes(
        [_decision()],
        _all_bars(rows),
        as_of_date="2026-07-10",
    )
    rth = next(row for row in outcomes if row["horizon"] == "rth_close")
    assert rth["final_result"]["exit_reason"] == "invalidation_stop"
    assert rth["final_result"]["exit_price"] == 90.0
    assert rth["final_result"]["paper_pnl_usd"] < 0


def test_add_invalidation_applies_inside_execution_bar():
    rows = [
        _bar("2026-07-10", "10:05", 101.0, low=89.0),
        _bar("2026-07-10", "11:05", 105.0),
        _bar("2026-07-10", "15:55", 108.0),
    ]
    outcomes = build_intraday_outcomes(
        [_decision()],
        _all_bars(rows),
        as_of_date="2026-07-10",
    )
    rth = next(row for row in outcomes if row["horizon"] == "rth_close")
    assert rth["final_result"]["exit_reason"] == "invalidation_stop"
    assert rth["final_result"]["exit_time"] == "2026-07-10 10:05:00"


def test_as_of_date_prevents_future_bar_settlement():
    outcomes = build_intraday_outcomes(
        [_decision()],
        _all_bars(_bars()),
        as_of_date="2026-07-10",
    )
    by_horizon = {row["horizon"]: row for row in outcomes}
    assert by_horizon["rth_close"]["status"] == "closed"
    assert by_horizon["next_close"]["status"] == "pending_horizon_bar"
    assert by_horizon["d3_close"]["status"] == "pending_horizon_bar"


def test_partial_execution_session_keeps_close_pending_but_h1_can_settle():
    rows = [
        _bar("2026-07-10", "10:05", 101.0),
        _bar("2026-07-10", "11:05", 102.0),
        _bar("2026-07-10", "13:05", 103.0),
    ]
    outcomes = build_intraday_outcomes(
        [_decision()],
        _all_bars(rows),
        as_of_date="2026-07-10",
    )
    by_horizon = {row["horizon"]: row for row in outcomes}
    assert by_horizon["h1"]["status"] == "closed"
    assert by_horizon["rth_close"]["status"] == "pending_horizon_bar"
    assert "horizon_time" not in by_horizon["rth_close"]


def test_partial_target_session_keeps_next_close_pending():
    rows = [
        _bar("2026-07-10", "10:05", 101.0),
        _bar("2026-07-10", "15:55", 102.0),
        _bar("2026-07-13", "09:30", 103.0),
        _bar("2026-07-13", "13:05", 104.0),
    ]
    outcomes = build_intraday_outcomes(
        [_decision()],
        _all_bars(rows),
        as_of_date="2026-07-13",
    )
    by_horizon = {row["horizon"]: row for row in outcomes}
    assert by_horizon["rth_close"]["status"] == "closed"
    assert by_horizon["next_close"]["status"] == "pending_horizon_bar"


def test_missing_expected_session_does_not_shift_horizon_forward():
    rows = [
        _bar("2026-07-10", "10:05", 101.0),
        _bar("2026-07-10", "15:55", 102.0),
        # Monday 2026-07-13 is the expected next session but is missing.
        _bar("2026-07-14", "15:55", 104.0),
        _bar("2026-07-15", "15:55", 105.0),
    ]
    outcomes = build_intraday_outcomes(
        [_decision()],
        _all_bars(rows),
        as_of_date="2026-07-15",
    )
    by_horizon = {row["horizon"]: row for row in outcomes}
    assert by_horizon["next_close"]["status"] == "pending_horizon_bar"


def test_early_close_without_calendar_contract_fails_closed():
    rows = [
        _bar("2026-07-10", "10:05", 101.0),
        _bar("2026-07-10", "12:55", 102.0),
    ]
    outcomes = build_intraday_outcomes(
        [_decision()],
        _all_bars(rows),
        as_of_date="2026-07-10",
    )
    rth = next(row for row in outcomes if row["horizon"] == "rth_close")
    assert rth["status"] == "pending_horizon_bar"


def test_migration_demotes_legacy_partial_close_and_drops_derived_values():
    legacy = {
        "schema_version": 1,
        "record_type": "intraday_triage_outcome",
        "outcome_rule_version": "intraday_triage_counterfactual_outcome_v1",
        "execution_rule_version": "intraday_triage_next_5m_execution_v1",
        "observation_id": "obs-legacy",
        "ticker": "NVDA",
        "decision_date": "2026-07-23",
        "decision_timestamp": "2026-07-23 13:00:00",
        "primary_ticker_day_decision": True,
        "horizon": "next_close",
        "status": "closed",
        "execution_time": "2026-07-23 13:05:00",
        "execution_price": 100.0,
        "horizon_time": "2026-07-24 13:05:00",
        "horizon_price": 101.0,
        "incremental_pnl_vs_no_adjustment_usd": 25.0,
        "final_result": {"paper_pnl_usd": 25.0},
    }
    migrated = migrate_intraday_outcomes_to_current_rule([legacy])[0]
    assert migrated["status"] == "pending_horizon_bar"
    assert migrated["outcome_rule_version"].endswith("_v2")
    assert "horizon_time" not in migrated
    assert "horizon_price" not in migrated
    assert "incremental_pnl_vs_no_adjustment_usd" not in migrated
    assert "final_result" not in migrated


def test_scorecard_defensively_excludes_legacy_partial_close():
    legacy = {
        **_decision(),
        "decision_timestamp": "2026-07-23 13:00:00",
        "primary_ticker_day_decision": True,
        "horizon": "next_close",
        "status": "closed",
        "execution_time": "2026-07-23 13:05:00",
        "horizon_time": "2026-07-24 13:05:00",
        "incremental_pnl_vs_no_adjustment_usd": 25.0,
    }
    scorecard = build_scorecard(
        [legacy],
        decisions=[_decision()],
        source_files=[],
        skipped_sources=[],
        as_of_date="2026-07-24",
        price_source={"status": "provided"},
    )
    next_close = scorecard["horizons"]["next_close"]
    assert next_close["raw_closed"] == 0
    assert next_close["closed"] == 0
    assert next_close["pending"] == 1
    assert scorecard["settlement_integrity"]["partial_close_rows_demoted"] == 1


def test_missing_position_value_is_not_scored_with_fallback_notional():
    decision = _decision()
    decision["paper_execution"]["position_market_value_at_decision"] = None
    outcomes = build_intraday_outcomes(
        [decision],
        _all_bars(_bars()),
        as_of_date="2026-07-10",
    )
    rth = next(row for row in outcomes if row["horizon"] == "rth_close")
    assert rth["status"] == "missing_position_value"
    assert "incremental_pnl_vs_no_adjustment_usd" not in rth


def _write_finalized(path: Path, timestamp: str, *, action="WAIT"):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "finalized_discretionary_forward_decision",
        "finalized_at_et": timestamp,
        "rows": [{
            **_decision(action, "WAIT"),
            "timestamp_et": timestamp,
        }],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_loader_marks_only_first_ticker_day_decision_primary(tmp_path):
    decision_dir = tmp_path / "daily" / "intraday" / "decisions"
    _write_finalized(decision_dir / "intraday_triage_20260710_100000ET.json", "2026-07-10 10:00 ET")
    _write_finalized(decision_dir / "intraday_triage_20260710_110000ET.json", "2026-07-10 11:00 ET")
    rows, files, skipped = load_finalized_decisions(tmp_path, through_date="2026-07-10")
    assert len(rows) == 2
    assert len(files) == 2
    assert skipped == []
    assert [row["primary_ticker_day_decision"] for row in rows] == [True, False]


def test_zero_row_backtest_writes_explicit_readiness_artifacts(tmp_path):
    result = run_intraday_backtest(
        "2026-07-11",
        data_dir=tmp_path,
        bars_by_ticker={},
    )
    scorecard = result["scorecard"]
    assert scorecard["status"] == "no_finalized_decisions"
    assert scorecard["readiness"]["evidence_stage"] == "case_review_only"
    assert scorecard["readiness"]["alpha_claim_allowed"] is False
    for path in result["paths"].values():
        assert Path(path).exists()


def test_scorecard_normalizes_daily_pnl_by_original_position_value(tmp_path):
    decision_dir = tmp_path / "daily" / "intraday" / "decisions"
    _write_finalized(
        decision_dir / "intraday_triage_20260710_100000ET.json",
        "2026-07-10 10:00 ET",
        action="ADD_SMALL",
    )
    result = run_intraday_backtest(
        "2026-07-13",
        data_dir=tmp_path,
        bars_by_ticker=_all_bars(_bars()),
    )
    curve = result["scorecard"]["daily_portfolio_curve_next_close"]
    assert curve["days"] == 1
    assert curve["curve"][0]["position_value_base_usd"] == 10_000.0
    assert curve["curve"][0]["daily_incremental_return_bps"] > 0


def test_scorecard_keeps_latest_decision_for_shared_execution_cohort(tmp_path):
    decision_dir = tmp_path / "daily" / "intraday" / "decisions"
    _write_finalized(
        decision_dir / "intraday_triage_20260711_100000ET.json",
        "2026-07-11 10:00 ET",
        action="ADD_SMALL",
    )
    _write_finalized(
        decision_dir / "intraday_triage_20260712_100000ET.json",
        "2026-07-12 10:00 ET",
        action="WAIT",
    )

    result = run_intraday_backtest(
        "2026-07-14",
        data_dir=tmp_path,
        bars_by_ticker=_all_bars(_bars()),
    )

    next_close = result["scorecard"]["horizons"]["next_close"]
    readiness = result["scorecard"]["readiness"]
    assert next_close["raw_rows"] == 2
    assert next_close["rows"] == 1
    assert next_close["raw_closed"] == 2
    assert next_close["closed"] == 1
    assert next_close["pending"] == 0
    assert next_close["duplicate_economic_cohorts"] == 1
    assert next_close["duplicate_rows_excluded"] == 1
    assert next_close["action_counts"] == {"WAIT": 1}
    assert next_close["incremental_pnl_vs_no_adjustment_usd"]["sum"] == 0.0
    assert readiness["raw_settled_primary_next_close_decisions"] == 2
    assert readiness["settled_primary_next_close_decisions"] == 1
    assert readiness["duplicate_settled_economic_rows_excluded"] == 1
    assert result["scorecard"]["daily_portfolio_curve_next_close"]["days"] == 1
