"""Parity + behavior tests for the co-ownership peer-shock paper sleeve.

Proves the relation actually binds (a co-ownership edge is required, not just a
peer shock + laggard momentum setup) and that the daily snapshot and historical
replay share the rule version and admit the same representative candidate.
"""

import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

import coownership_peer_shock_paper_sleeve as cps  # noqa: E402


SIGNAL_IDX = 65
N_DAYS = 80


def _dates() -> list[str]:
    start = date(2024, 10, 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(N_DAYS)]


def _flat_rows(dates, close, *, volume, signal_overrides=None):
    rows = []
    for i, day in enumerate(dates):
        row = {
            "date": day,
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": volume,
        }
        if signal_overrides and i == SIGNAL_IDX:
            row.update(signal_overrides)
        rows.append(row)
    return rows


def _synthetic_ohlcv():
    dates = _dates()
    spy = _flat_rows(dates, 400.0, volume=80_000_000)
    # PEERX: sharp idiosyncratic up-move on the signal day, on heavy volume.
    peer = _flat_rows(
        dates,
        100.0,
        volume=1_000_000,
        signal_overrides={"open": 101.0, "high": 108.5, "low": 100.5, "close": 108.0, "volume": 1_500_000},
    )
    # LAGX: flat laggard, small positive close, mid-upper close location.
    lag = _flat_rows(
        dates,
        100.0,
        volume=1_000_000,
        signal_overrides={"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.2, "volume": 1_000_000},
    )
    return {"SPY": spy, "PEERX": peer, "LAGX": lag}, dates


def _sector_entries():
    return {
        "PEERX": {"sector": "Technology", "industry": "Semiconductors", "sector_coverage_status": "ok"},
        "LAGX": {"sector": "Technology", "industry": "Semiconductors", "sector_coverage_status": "ok"},
    }


class _StubProvider:
    """Co-ownership graph where PEERX and LAGX are connected peers."""

    def __init__(self, *, lift=3.2, shared=40):
        self._edges = {
            "PEERX": {"LAGX": {"peer": "LAGX", "shared_managers": shared, "lift": lift, "jaccard": 0.21}},
            "LAGX": {"PEERX": {"peer": "PEERX", "shared_managers": shared, "lift": lift, "jaccard": 0.21}},
        }

    @property
    def labels(self):
        return ["stub_window"]

    def peers_for_date(self, signal_date):
        return self._edges


def _core_by_date(signal_date):
    # A core entry exists on the signal day (core-flow confirmation), on a
    # different ticker than the laggard so there is no same-ticker overlap.
    return {signal_date: [{"ticker": "COREZ"}]}


def test_historical_admits_coowned_laggard():
    ohlcv, dates = _synthetic_ohlcv()
    signal_date = dates[SIGNAL_IDX]
    trades, audit = cps.build_coownership_peer_shock_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date=_core_by_date(signal_date),
        windows={"test": {"start": dates[0], "end": dates[-1]}},
        sector_entries=_sector_entries(),
        edge_provider=_StubProvider(),
    )
    assert len(trades) == 1, audit["scan_by_window"]["test"]
    trade = trades[0]
    assert trade["ticker"] == "LAGX"
    assert trade["peer_ticker"] == "PEERX"
    assert trade["coownership_shared_managers"] == 40
    assert trade["coownership_lift"] == 3.2
    assert trade["rule_version"] == cps.RULE_VERSION
    assert trade["trade_enabled"] is False
    assert "pnl" in trade and "entry_date" in trade and "exit_date" in trade


def test_relation_gate_binds_no_edge_no_candidate():
    """Same peer-shock + laggard setup, but no co-ownership edge -> no admit.

    This is the discriminating test: it proves admission is driven by the
    co-ownership relation, not merely by the shared peer-shock/laggard momentum
    screen (which is identical to the rolling-corr sleeve).
    """
    ohlcv, dates = _synthetic_ohlcv()
    signal_date = dates[SIGNAL_IDX]

    class _EmptyProvider:
        labels = []

        def peers_for_date(self, signal_date):
            return {}

    trades, _ = cps.build_coownership_peer_shock_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date=_core_by_date(signal_date),
        windows={"test": {"start": dates[0], "end": dates[-1]}},
        sector_entries=_sector_entries(),
        edge_provider=_EmptyProvider(),
    )
    assert trades == []


def test_lift_floor_binds():
    """An edge below the lift floor (just both widely held) is not admitted."""
    ohlcv, dates = _synthetic_ohlcv()
    signal_date = dates[SIGNAL_IDX]
    trades, _ = cps.build_coownership_peer_shock_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date=_core_by_date(signal_date),
        windows={"test": {"start": dates[0], "end": dates[-1]}},
        sector_entries=_sector_entries(),
        edge_provider=_StubProvider(lift=0.9),  # below min_coownership_lift=1.5
    )
    assert trades == []


def test_daily_snapshot_parity_with_replay():
    """Daily default-off snapshot admits the same candidate as replay and shares
    the source rule version (production-visibility/backtest parity)."""
    ohlcv, dates = _synthetic_ohlcv()
    signal_date = dates[SIGNAL_IDX]
    snapshot = cps.build_coownership_peer_shock_paper_sleeve_snapshot(
        as_of=signal_date,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "COREZ"}],
        sector_entries=_sector_entries(),
        state=cps.empty_coownership_peer_shock_paper_state(),
        edge_provider=_StubProvider(),
        persist=False,
    )
    assert snapshot["trade_enabled"] is False
    assert snapshot["source_rule_version"] == cps.SOURCE_RULE_VERSION
    assert snapshot["candidate_count"] == 1
    cand = snapshot["candidates"][0]
    assert cand["ticker"] == "LAGX"
    assert cand["peer_ticker"] == "PEERX"
    # Replay shares the exact source rule version -> shared-helper parity.
    _, audit = cps.build_coownership_peer_shock_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date=_core_by_date(signal_date),
        windows={"w": {"start": dates[0], "end": dates[-1]}},
        sector_entries=_sector_entries(),
        edge_provider=_StubProvider(),
    )
    assert audit["source_rule_version"] == snapshot["source_rule_version"]


def test_production_impact_is_default_off():
    snap = cps.empty_coownership_peer_shock_paper_sleeve_snapshot("2026-06-21", "missing_ohlcv")
    impact = snap["production_impact"]
    assert impact["trade_enabled"] is False
    assert impact["alters_orders"] is False
    assert impact["alters_candidate_ranking"] is False
    assert impact["shared_policy_changed"] is False


def test_edge_provider_pit_resolution(tmp_path):
    """Real provider resolves the newest window whose filing window ended on or
    before the signal day, and returns nothing before any window exists."""
    payload = {
        "peers_by_ticker": {
            "A": [{"peer": "KEYS", "shared_managers": 32, "lift": 7.37, "jaccard": 0.18}],
        }
    }
    (tmp_path / "coownership_edges_01jun2024-31aug2024.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    (tmp_path / "coownership_edges_01dec2024-28feb2025.json").write_text(
        json.dumps({"peers_by_ticker": {"A": [{"peer": "IQV", "shared_managers": 30, "lift": 3.9}]}}),
        encoding="utf-8",
    )
    provider = cps.CoownershipEdgeProvider(edges_dir=tmp_path)
    assert provider.labels == ["01jun2024-31aug2024", "01dec2024-28feb2025"]
    # Before any window: empty.
    assert provider.peers_for_date("2024-01-01") == {}
    # Between the two windows: the older one resolves.
    mid = provider.peers_for_date("2024-10-15")
    assert "KEYS" in mid["A"]
    # After the newer window closes: the newer one resolves.
    late = provider.peers_for_date("2025-06-01")
    assert "IQV" in late["A"]
