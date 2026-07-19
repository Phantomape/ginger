from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import ortex_borrow_observer as observer
import ortex_data_sidecar as sidecar


def _source_row(
    ticker: str = "AAPL",
    provider_date: str = "2026-06-30",
    usable_trade_date: str = "2026-07-01",
    value: float = 3.0,
) -> dict:
    return {
        "schema_version": 1,
        "ticker": ticker,
        "exchange": "NASDAQ",
        "provider_date": provider_date,
        "usable_trade_date": usable_trade_date,
        "cost_to_borrow_new_pct": value,
        "collected_at": "2026-07-18T00:00:00Z",
        "source_mode": "historical_block",
        "source": "ortex_api_cost_to_borrow_new",
        "trade_enabled": False,
    }


def _price_history() -> tuple[dict, list[str]]:
    sessions = [(date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(12)]
    prices: dict[str, dict[str, dict[str, float]]] = {}
    for ticker in ("AAPL", "MSFT", "SPY", "QQQ"):
        prices[ticker] = {
            day: {"Open": 100.0, "Close": 100.0} for day in sessions
        }
    prices["AAPL"][sessions[5]]["Close"] = 110.0
    prices["AAPL"][sessions[10]]["Close"] = 120.0
    prices["MSFT"][sessions[5]]["Close"] = 90.0
    prices["MSFT"][sessions[10]]["Close"] = 80.0
    prices["SPY"][sessions[5]]["Close"] = 105.0
    prices["SPY"][sessions[10]]["Close"] = 110.0
    prices["QQQ"][sessions[5]]["Close"] = 102.0
    prices["QQQ"][sessions[10]]["Close"] = 104.0
    return prices, sessions


def test_daily_snapshot_uses_latest_legally_usable_row() -> None:
    rows = [
        _source_row(provider_date="2026-06-30", usable_trade_date="2026-07-01", value=1.0),
        _source_row(provider_date="2026-07-01", usable_trade_date="2026-07-02", value=2.0),
        _source_row(provider_date="2026-07-02", usable_trade_date="2026-07-03", value=99.0),
    ]
    snapshot = observer.build_daily_snapshot(
        rows,
        as_of="2026-07-02",
        tickers=("AAPL", "MSFT"),
        generated_at="2026-07-02T22:00:00Z",
    )
    assert snapshot["coverage_count"] == 1
    assert snapshot["missing_tickers"] == ["MSFT"]
    assert snapshot["observations"][0]["provider_date"] == "2026-07-01"
    assert snapshot["observations"][0]["cost_to_borrow_new_pct"] == 2.0
    assert snapshot["trade_enabled"] is False
    assert snapshot["strategy_behavior_changed"] is False


def test_daily_snapshot_embeds_shared_default_off_entry_admission_parity() -> None:
    sessions = [
        "2026-06-30",
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
    ]
    rows = [
        _source_row(
            provider_date=sessions[0],
            usable_trade_date=sessions[1],
            value=0.20,
        ),
        _source_row(
            provider_date=sessions[1],
            usable_trade_date=sessions[2],
            value=1.00,
        ),
    ]
    snapshot = observer.build_daily_snapshot(
        rows,
        as_of=sessions[1],
        tickers=("AAPL", "MSFT"),
        generated_at="2026-07-01T22:00:00Z",
        trading_sessions=sessions,
    )

    admission = snapshot["entry_admission"]
    assert admission["next_trading_session"] == sessions[2]
    assert admission["excluded_tickers_for_next_session"] == ["AAPL"]
    assert admission["eligible_tickers"] == ["MSFT"]
    assert admission["covered_tickers"] == ["AAPL"]
    assert admission["missing_tickers"] == ["MSFT"]
    assert admission["alternate_delta_availability_branch_available"] is False
    assert admission["missing_policy_fields"] == ["availability"]
    assert admission["trade_enabled"] is False
    assert admission["strategy_behavior_changed"] is False
    assert admission["alters_live_orders"] is False


def test_generic_h5_h10_outcomes_settle_cash_spy_qqq_without_selection() -> None:
    prices, sessions = _price_history()
    rows = [
        _source_row("AAPL", value=3.0),
        _source_row("MSFT", value=-1.0),
    ]
    outcomes, summary = observer.build_generic_horizon_outcomes(
        rows,
        prices,
        as_of=sessions[-1],
        horizons=(5, 10),
        notional_usd=1000,
    )
    assert len(outcomes) == 4
    assert summary["candidate_outcome_count"] == 4
    assert summary["settled_count"] == 4
    # The negative CTB row is not filtered: this surface measures all rows.
    assert {row["ticker"] for row in outcomes} == {"AAPL", "MSFT"}
    aapl_h5 = next(
        row for row in outcomes if row["ticker"] == "AAPL" and row["horizon_trading_days"] == 5
    )
    assert aapl_h5["entry_date"] == sessions[0]
    assert aapl_h5["exit_date"] == sessions[5]
    assert aapl_h5["ticker_return_pct"] == 10.0
    assert aapl_h5["replacement_value_vs_cash_usd"] == 100.0
    assert aapl_h5["replacement_value_vs_spy_usd"] == 50.0
    assert aapl_h5["replacement_value_vs_qqq_usd"] == 80.0
    assert all(row["trade_enabled"] is False for row in outcomes)


def test_price_normaliser_accepts_dataframe_like_datetime_index_without_pandas_dependency() -> None:
    class FrameLike:
        def __init__(self, rows):
            self.rows = rows

        def iterrows(self):
            yield from self.rows

    sessions = [(date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(7)]
    frame = FrameLike(
        [(day + "T00:00:00", {"Open": 100.0, "Close": 110.0 if index == 5 else 100.0})
         for index, day in enumerate(sessions)]
    )
    prices = {"AAPL": frame, "SPY": frame, "QQQ": frame}
    outcomes, summary = observer.build_generic_horizon_outcomes(
        [_source_row()], prices, as_of=sessions[-1], horizons=(5,)
    )
    assert summary["settled_count"] == 1
    assert outcomes[0]["entry_date"] == sessions[0]
    assert outcomes[0]["exit_date"] == sessions[5]
    assert outcomes[0]["ticker_return_pct"] == 10.0


def test_outcomes_remain_unsettled_until_both_comparators_and_horizon_exist() -> None:
    prices, sessions = _price_history()
    del prices["QQQ"][sessions[5]]
    outcomes, summary = observer.build_generic_horizon_outcomes(
        [_source_row()], prices, as_of=sessions[5], horizons=(5, 10)
    )
    assert outcomes == []
    assert summary["settled_count"] == 0
    assert summary["status_counts"] == {
        "missing_aligned_price": 1,
        "unsettled_horizon": 1,
    }


def test_local_cycle_is_atomic_idempotent_default_off_and_never_calls_network(tmp_path: Path) -> None:
    rows_path = tmp_path / "rows.jsonl"
    snapshot_ledger = tmp_path / "snapshots.jsonl"
    latest_snapshot = tmp_path / "latest_snapshot.json"
    outcome_ledger = tmp_path / "outcomes.jsonl"
    outcome_summary = tmp_path / "latest_outcomes.json"
    sidecar.append_normalised_rows_atomic([_source_row()], path=rows_path)
    prices, sessions = _price_history()

    def forbidden_fetch(**kwargs):  # pragma: no cover - assertion path only
        raise AssertionError(f"network fetch was invoked: {kwargs}")

    kwargs = {
        "as_of": sessions[-1],
        "price_history_by_ticker": prices,
        "refresh_network": False,
        "tickers": ("AAPL",),
        "rows_path": rows_path,
        "snapshot_ledger_path": snapshot_ledger,
        "latest_snapshot_path": latest_snapshot,
        "outcome_ledger_path": outcome_ledger,
        "latest_outcome_summary_path": outcome_summary,
        "fetcher": forbidden_fetch,
        "collected_at": "2026-07-18T00:00:00Z",
    }
    first = observer.run_ortex_borrow_observer_cycle(**kwargs)
    second = observer.run_ortex_borrow_observer_cycle(**kwargs)
    assert first["network_refresh"]["status"] == "disabled"
    assert first["snapshot_ledger_merge"]["appended"] == 1
    assert first["outcome_ledger_merge"]["appended"] == 2
    assert second["snapshot_ledger_merge"]["appended"] == 0
    assert second["outcome_ledger_merge"]["appended"] == 0
    assert len(observer._load_jsonl(snapshot_ledger)) == 1
    assert len(observer._load_jsonl(outcome_ledger)) == 2
    assert first["trade_enabled"] is False
    assert json.loads(latest_snapshot.read_text(encoding="utf-8"))["trade_enabled"] is False
    assert json.loads(outcome_summary.read_text(encoding="utf-8"))["trade_enabled"] is False


def test_cycle_forwards_bounded_refresh_controls(monkeypatch, tmp_path: Path) -> None:
    rows_path = tmp_path / "rows.jsonl"
    captured: dict = {}

    def fake_refresh(**kwargs):
        captured.update(kwargs)
        return {
            "status": "completed",
            "requests_made": 0,
            "rows_appended": 0,
            "trade_enabled": False,
        }

    monkeypatch.setattr(sidecar, "materialize_daily_refresh", fake_refresh)
    result = observer.run_ortex_borrow_observer_cycle(
        as_of="2026-07-18",
        refresh_network=True,
        trading_dates=["2026-07-18", "2026-07-20"],
        rows_path=rows_path,
        snapshot_ledger_path=tmp_path / "snapshots.jsonl",
        latest_snapshot_path=tmp_path / "latest_snapshot.json",
        outcome_ledger_path=tmp_path / "outcomes.jsonl",
        latest_outcome_summary_path=tmp_path / "outcome_summary.json",
        max_refresh_tickers=4,
        min_refresh_age_days=5,
        min_credits_left=250,
    )
    assert captured["max_refresh_tickers"] == 4
    assert captured["min_refresh_age_days"] == 5
    assert captured["min_credits_left"] == 250
    assert result["trade_enabled"] is False
