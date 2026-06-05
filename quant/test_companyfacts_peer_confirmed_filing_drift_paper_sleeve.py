from __future__ import annotations

from datetime import date, timedelta

from quant.companyfacts_peer_confirmed_filing_drift_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_companyfacts_peer_confirmed_historical_trades,
    build_companyfacts_peer_confirmed_paper_sleeve_snapshot,
    empty_companyfacts_peer_confirmed_paper_state,
)


def _trading_rows(
    *,
    base: float,
    step: float,
    days: int = 150,
    volume: float = 2_000_000.0,
) -> list[dict]:
    current = date(2026, 1, 1)
    rows = []
    while len(rows) < days:
        if current.weekday() < 5:
            idx = len(rows)
            close = base + step * idx
            rows.append(
                {
                    "date": current.isoformat(),
                    "open": round(close * 0.998, 4),
                    "high": round(close * 1.004, 4),
                    "low": round(close * 0.986, 4),
                    "close": round(close, 4),
                    "volume": volume,
                }
            )
        current += timedelta(days=1)
    return rows


def _ohlcv() -> dict[str, list[dict]]:
    return {
        "SPY": _trading_rows(base=100.0, step=0.04, volume=20_000_000.0),
        "AMD": _trading_rows(base=80.0, step=0.34, volume=1_500_000.0),
        "NVDA": _trading_rows(base=140.0, step=0.12, volume=1_200_000.0),
        "AAPL": _trading_rows(base=170.0, step=0.02, volume=1_000_000.0),
    }


def _growth(ticker: str, canonical: str, asof: str, growth: float) -> dict:
    return {
        "ticker": ticker,
        "canonical": canonical,
        "asof_date": asof,
        "growth_status": "ok",
        "yoy_growth": growth,
        "current_value": 125.0,
        "prior_value": 100.0,
        "current_form": "10-Q",
        "current_fy": 2026,
        "current_fp": "Q1",
        "current_period_end": "2026-03-31",
    }


def _facts(as_of: str, *, include_peer: bool = True) -> list[dict]:
    filed = (date.fromisoformat(as_of) - timedelta(days=10)).isoformat()
    rows = [
        _growth("AMD", "revenue", filed, 0.26),
        _growth("AMD", "eps_diluted", filed, 0.45),
    ]
    if include_peer:
        rows.extend(
            [
                _growth("NVDA", "revenue", filed, 0.18),
                _growth("NVDA", "eps_diluted", filed, 0.24),
            ]
        )
    return rows


def _sector_cache() -> dict:
    return {
        "schema_version": 1,
        "entries": {
            "AMD": {
                "sector": "Technology",
                "industry": "Semiconductors",
                "status": "ok",
            },
            "NVDA": {
                "sector": "Technology",
                "industry": "Semiconductors",
                "status": "ok",
            },
            "AAPL": {
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "status": "ok",
            },
        },
    }


def test_snapshot_adds_peer_confirmed_companyfacts_candidate_without_orders(monkeypatch):
    from quant import companyfacts_peer_confirmed_filing_drift_paper_sleeve as sleeve

    monkeypatch.setattr(sleeve.broad_market_sector_map, "load_cache", lambda: _sector_cache())
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][90]["date"]

    snapshot = build_companyfacts_peer_confirmed_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["AMD", "NVDA", "AAPL"],
        companyfacts_growth_rows=_facts(as_of),
        state=empty_companyfacts_peer_confirmed_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False
    assert snapshot["production_impact"]["alters_signal_generation"] is False
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "AMD"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["source_rule_version"] == SOURCE_RULE_VERSION
    assert candidate["peer_relation_type"] == "same_industry_recent_dual_growth"
    assert candidate["peer_confirmation_count"] == 1
    assert candidate["peer_confirmation_tickers"] == ["NVDA"]
    assert candidate["intended_notional"] == 4_000.0


def test_candidate_requires_recent_same_industry_peer_confirmation(monkeypatch):
    from quant import companyfacts_peer_confirmed_filing_drift_paper_sleeve as sleeve

    monkeypatch.setattr(sleeve.broad_market_sector_map, "load_cache", lambda: _sector_cache())
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][90]["date"]

    snapshot = build_companyfacts_peer_confirmed_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["AMD", "NVDA", "AAPL"],
        companyfacts_growth_rows=_facts(as_of, include_peer=False),
        state=empty_companyfacts_peer_confirmed_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["peer_confirmation"]["peer_rejected_count"] >= 1
    assert snapshot["trade_enabled"] is False


def test_historical_replay_and_daily_snapshot_share_rule_versions(monkeypatch):
    from quant import companyfacts_peer_confirmed_filing_drift_paper_sleeve as sleeve

    monkeypatch.setattr(sleeve.broad_market_sector_map, "load_cache", lambda: _sector_cache())
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][90]["date"]
    windows = {
        "fixture": {
            "start": signal_day,
            "end": ohlcv["SPY"][92]["date"],
        }
    }

    trades, audit = build_companyfacts_peer_confirmed_historical_trades(
        ohlcv_by_ticker=ohlcv,
        companyfacts_growth_rows=_facts(signal_day),
        windows=windows,
    )
    snapshot = build_companyfacts_peer_confirmed_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["AMD", "NVDA", "AAPL"],
        companyfacts_growth_rows=_facts(signal_day),
        state=empty_companyfacts_peer_confirmed_paper_state(),
        persist=False,
    )

    assert trades
    assert trades[0]["ticker"] == snapshot["candidates"][0]["ticker"]
    assert trades[0]["rule_version"] == snapshot["candidates"][0]["rule_version"] == RULE_VERSION
    assert trades[0]["source_rule_version"] == SOURCE_RULE_VERSION
    assert audit["selected_by_window"]["fixture"] >= 1
    assert snapshot["production_impact"]["backtester_adapter_changed"] is False
