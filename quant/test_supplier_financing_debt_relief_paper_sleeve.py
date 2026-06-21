from __future__ import annotations

from datetime import date, timedelta

import pytest

from quant.supplier_financing_debt_relief_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_supplier_financing_debt_relief_historical_trades,
    build_supplier_financing_debt_relief_paper_sleeve_snapshot,
    empty_supplier_financing_debt_relief_state,
)


def _business_dates(days: int) -> list[str]:
    current = date(2026, 1, 1)
    out: list[str] = []
    while len(out) < days:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _returns(kind: str, days: int = 88, signal_day: int = 70) -> list[float]:
    values = [0.0004 for _ in range(days)]
    if kind == "spy":
        values[signal_day] = 0.001
        return values
    if kind == "leader":
        for idx in range(signal_day - 60, signal_day):
            values[idx] = 0.0018
        values[signal_day] = 0.024
        values[signal_day + 1 : signal_day + 11] = [0.0045] * 10
        return values
    if kind == "weak":
        for idx in range(signal_day - 60, signal_day):
            values[idx] = 0.0014
        values[signal_day] = 0.018
        return values
    raise AssertionError(kind)


def _rows(*, base: float, returns: list[float], signal_day: int, volume: float) -> list[dict]:
    rows: list[dict] = []
    close = base
    days = _business_dates(len(returns))
    for idx, day in enumerate(days):
        prior_close = close
        ret = returns[idx]
        open_ = prior_close
        close = prior_close * (1.0 + ret)
        if idx == signal_day:
            low = min(open_, close) * 0.992
            high = close * 1.003
            volume_mult = 1.20
        else:
            low = min(open_, close) * 0.996
            high = max(open_, close) * 1.004
            volume_mult = 1.0
        rows.append(
            {
                "date": day,
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume * volume_mult,
            }
        )
    return rows


def _ohlcv(days: int = 88) -> dict[str, list[dict]]:
    signal_day = 70
    return {
        "SPY": _rows(
            base=100.0,
            returns=_returns("spy", days, signal_day),
            signal_day=signal_day,
            volume=1_000_000.0,
        ),
        "LEAD": _rows(
            base=90.0,
            returns=_returns("leader", days, signal_day),
            signal_day=signal_day,
            volume=700_000.0,
        ),
        "WEAK": _rows(
            base=80.0,
            returns=_returns("weak", days, signal_day),
            signal_day=signal_day,
            volume=800_000.0,
        ),
    }


def _payables_facts(*, improved: bool = True) -> dict[str, list[dict]]:
    current_payables = 260_000_000.0 if improved else 115_000_000.0
    return {
        "payables": [
            {
                "tag": "AccountsPayableCurrent",
                "end": "2024-09-30",
                "filed": "2024-11-05",
                "value": 100_000_000.0,
            },
            {
                "tag": "AccountsPayableCurrent",
                "end": "2024-12-31",
                "filed": "2025-02-20",
                "value": 105_000_000.0,
            },
            {
                "tag": "AccountsPayableCurrent",
                "end": "2025-09-30",
                "filed": "2025-11-05",
                "value": 200_000_000.0,
            },
            {
                "tag": "AccountsPayableCurrent",
                "end": "2025-12-31",
                "filed": "2026-02-20",
                "value": current_payables,
            },
        ],
        "cogs": [
            {
                "tag": "CostOfRevenue",
                "start": "2024-10-01",
                "end": "2024-12-31",
                "filed": "2025-02-20",
                "value": 450_000_000.0,
                "duration_days": 92,
            },
            {
                "tag": "CostOfRevenue",
                "start": "2025-10-01",
                "end": "2025-12-31",
                "filed": "2026-02-20",
                "value": 520_000_000.0,
                "duration_days": 92,
            },
        ],
        "gross_profit": [
            {
                "tag": "GrossProfit",
                "start": "2024-10-01",
                "end": "2024-12-31",
                "filed": "2025-02-20",
                "value": 180_000_000.0,
                "duration_days": 92,
            },
            {
                "tag": "GrossProfit",
                "start": "2025-10-01",
                "end": "2025-12-31",
                "filed": "2026-02-20",
                "value": 220_000_000.0,
                "duration_days": 92,
            },
        ],
    }


def _debt_facts(*, improved: bool = True) -> dict[str, list[dict]]:
    current_debt = 210_000_000.0 if improved else 420_000_000.0
    return {
        "debt_total": [
            {
                "tag": "LongTermDebtAndFinanceLeaseObligations",
                "end": "2024-12-31",
                "filed": "2025-02-20",
                "value": 360_000_000.0,
            },
            {
                "tag": "LongTermDebtAndFinanceLeaseObligations",
                "end": "2025-12-31",
                "filed": "2026-02-20",
                "value": current_debt,
            },
        ],
        "debt_current": [],
        "debt_noncurrent": [],
        "revenue": [
            {
                "tag": "Revenues",
                "start": "2024-01-01",
                "end": "2024-12-31",
                "filed": "2025-02-20",
                "value": 900_000_000.0,
                "duration_days": 365,
            },
            {
                "tag": "Revenues",
                "start": "2025-01-01",
                "end": "2025-12-31",
                "filed": "2026-02-20",
                "value": 1_050_000_000.0,
                "duration_days": 365,
            },
        ],
    }


def _quality_index() -> dict[str, dict[str, dict[str, list[dict]]]]:
    return {
        "LEAD": {
            "payables": _payables_facts(improved=True),
            "debt": _debt_facts(improved=True),
        },
        "WEAK": {
            "payables": _payables_facts(improved=False),
            "debt": _debt_facts(improved=False),
        },
    }


def _sector_entries() -> dict[str, dict]:
    return {
        "LEAD": {"sector": "Industrials", "industry": "Machinery", "sector_coverage_status": "ok"},
        "WEAK": {"sector": "Industrials", "industry": "Machinery", "sector_coverage_status": "ok"},
    }


def test_snapshot_normalises_indexed_dataframe_ohlcv() -> None:
    pd = pytest.importorskip("pandas")
    full_ohlcv = _ohlcv()
    signal_day = full_ohlcv["SPY"][70]["date"]
    truncated = {ticker: rows[:71] for ticker, rows in full_ohlcv.items()}
    indexed = {
        ticker: pd.DataFrame(rows).set_index("date")
        for ticker, rows in truncated.items()
    }

    snapshot = build_supplier_financing_debt_relief_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=indexed,
        quality_index=_quality_index(),
        sector_entries=_sector_entries(),
        state=empty_supplier_financing_debt_relief_state(),
        persist=False,
    )

    assert snapshot.get("error") is None
    assert snapshot["candidate_count"] == 1


def test_snapshot_creates_default_off_risk_scaled_pending_without_orders() -> None:
    full_ohlcv = _ohlcv()
    signal_day = full_ohlcv["SPY"][70]["date"]
    truncated = {ticker: rows[:71] for ticker, rows in full_ohlcv.items()}

    snapshot = build_supplier_financing_debt_relief_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=truncated,
        quality_index=_quality_index(),
        sector_entries=_sector_entries(),
        state=empty_supplier_financing_debt_relief_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "LEAD"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["source_rule_version"] == SOURCE_RULE_VERSION
    assert 0 < candidate["paper_notional_usd"] < 4_000.0
    assert candidate["risk_notional_scalar"] < 1.0


def test_historical_replay_and_daily_snapshot_share_candidate_decision() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    windows = {"fixture": {"start": signal_day, "end": ohlcv["SPY"][80]["date"]}}

    trades, audit = build_supplier_financing_debt_relief_historical_trades(
        ohlcv_by_ticker=ohlcv,
        windows=windows,
        quality_index=_quality_index(),
        sector_entries=_sector_entries(),
    )
    snapshot = build_supplier_financing_debt_relief_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        quality_index=_quality_index(),
        sector_entries=_sector_entries(),
        state=empty_supplier_financing_debt_relief_state(),
        persist=False,
    )

    assert len(trades) == 1
    assert trades[0]["ticker"] == snapshot["candidates"][0]["ticker"] == "LEAD"
    assert trades[0]["decision_id"] == snapshot["candidates"][0]["decision_id"]
    assert trades[0]["paper_notional_usd"] == snapshot["candidates"][0]["paper_notional_usd"]
    assert audit["selected_by_window"]["fixture"] == 1


def test_historical_replay_uses_next_open_and_10_day_close_fill() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    exit_day = ohlcv["SPY"][80]["date"]

    trades, _audit = build_supplier_financing_debt_relief_historical_trades(
        ohlcv_by_ticker=ohlcv,
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        quality_index=_quality_index(),
        sector_entries=_sector_entries(),
    )

    assert len(trades) == 1
    trade = trades[0]
    assert trade["entry_date"] == ohlcv["SPY"][71]["date"]
    assert trade["exit_date"] == exit_day
    assert trade["paper_status"] == "closed"
    assert trade["trade_enabled"] is False
    assert trade["pnl_pct_net"] > 0


def test_daily_snapshot_advances_pending_to_closed_using_same_decision_id(tmp_path) -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    state_path = tmp_path / "state.json"
    snapshot_log_path = tmp_path / "snapshots.jsonl"

    trades, _audit = build_supplier_financing_debt_relief_historical_trades(
        ohlcv_by_ticker=ohlcv,
        windows={"fixture": {"start": signal_day, "end": ohlcv["SPY"][80]["date"]}},
        quality_index=_quality_index(),
        sector_entries=_sector_entries(),
    )
    build_supplier_financing_debt_relief_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        quality_index=_quality_index(),
        sector_entries=_sector_entries(),
        state_path=state_path,
        snapshot_log_path=snapshot_log_path,
        persist=True,
    )
    closed_snapshot = {}
    for idx in range(71, 81):
        closed_snapshot = build_supplier_financing_debt_relief_paper_sleeve_snapshot(
            as_of=ohlcv["SPY"][idx]["date"],
            ohlcv_by_ticker=ohlcv,
            quality_index=_quality_index(),
            sector_entries=_sector_entries(),
            state_path=state_path,
            snapshot_log_path=snapshot_log_path,
            persist=True,
        )

    assert closed_snapshot["closed_count_today"] == 1
    closed = closed_snapshot["closed_positions_this_run"][0]
    assert closed["decision_id"] == trades[0]["decision_id"]
    assert closed["entry_date"] == trades[0]["entry_date"]
    assert closed["paper_notional_usd"] == trades[0]["paper_notional_usd"]
