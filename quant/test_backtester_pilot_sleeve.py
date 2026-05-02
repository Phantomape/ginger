import inspect
import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from backtester import BacktestEngine, Position  # noqa: E402
from pilot_sleeve import PILOT_SLEEVE_NAME  # noqa: E402


def test_backtester_default_remains_core_only_for_data_universe():
    engine = BacktestEngine(
        ["AAPL"],
        start="2026-05-01",
        end="2026-05-01",
        include_pilot_sleeve=False,
    )

    assert engine.include_pilot_sleeve is False
    assert engine._pilot_tickers_for_download() == []
    assert engine._backtest_data_universe() == ["AAPL"]


def test_backtester_preloads_pilot_data_only_when_pit_eligible():
    before = BacktestEngine(
        ["AAPL"],
        start="2026-04-01",
        end="2026-04-21",
        include_pilot_sleeve=True,
    )
    after = BacktestEngine(
        ["AAPL"],
        start="2026-05-01",
        end="2026-05-01",
        include_pilot_sleeve=True,
    )

    assert before._pilot_tickers_for_download() == []
    assert {"BE", "INTC", "LITE"}.issubset(after._pilot_tickers_for_download())
    assert {"AAPL", "BE", "INTC", "LITE"}.issubset(after._backtest_data_universe())


def test_position_can_carry_pilot_replay_metadata():
    snapshot = {"decision_id": "pilot-1", "counterfactuals": []}
    pos = Position(
        ticker="INTC",
        entry_price=100,
        entry_open_price=99.5,
        stop_price=95,
        target_price=110,
        shares=3,
        entry_date="2026-05-04",
        strategy="trend_long",
        sleeve=PILOT_SLEEVE_NAME,
        pilot_decision_id="pilot-1",
        pilot_snapshot=snapshot,
        pilot_signal_date="2026-05-01",
    )

    assert pos.sleeve == PILOT_SLEEVE_NAME
    assert pos.pilot_decision_id == "pilot-1"
    assert pos.pilot_snapshot is snapshot
    assert pos.pilot_signal_date == "2026-05-01"


def test_backtester_pilot_replay_does_not_write_production_decision_log():
    source = inspect.getsource(BacktestEngine.run)

    assert "append_pilot_decision_snapshots" not in source
    assert "append_decision_snapshot" not in source
