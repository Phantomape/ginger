"""Regression tests for the repo bug-audit fixes (branch claude/repo-bug-audit-2lNTw).

Each test pins a previously-crashing input path so the defensive guards do not
silently regress.
"""

import json

import pytest


def test_enrich_signals_handles_none_features_dict():
    """risk_engine.enrich_signals must not crash when features_dict is None.

    Previously lines 327/340/402 called ``features_dict.get(...)`` directly,
    raising AttributeError on None even though the rest of the function treats
    None as a valid 'no features' input.
    """
    from risk_engine import enrich_signals

    # No signals -> exercises the pre-loop SPY/dispersion/cutoff helpers only.
    assert enrich_signals([], None) == []

    # One signal with None features_dict -> exercises the per-signal loop guard.
    sig = {"ticker": "AAPL", "strategy": "trend_long", "confidence_score": 0.9}
    out = enrich_signals([sig], None)
    # Signal is dropped (no ATR) but the call must not raise.
    assert isinstance(out, list)


def test_generate_daily_report_handles_none_pct_from_ma():
    """report_generator must not crash when a regime index has close+ma200 but
    pct_from_ma is None (a tolerated partial regime computation)."""
    from report_generator import generate_daily_report

    market_regime = {
        "regime": "NEUTRAL",
        "indices": {
            "SPY": {"close": 500.0, "ma200": 480.0, "pct_from_ma": None, "above_ma": True},
        },
    }
    report = generate_daily_report([], market_regime=market_regime)
    assert isinstance(report, str)
    # The price/200MA line is still emitted; only the (+x%) suffix is omitted.
    assert "200MA" in report


def test_load_open_positions_tolerates_malformed_json(tmp_path, monkeypatch):
    """run_quant._load_open_positions degrades to None on malformed JSON instead
    of crashing the whole daily pipeline."""
    import run_quant

    bad = tmp_path / "open_positions.json"
    bad.write_text("{ this is not valid json ", encoding="utf-8")
    monkeypatch.setattr(run_quant, "open_positions_path", lambda: bad)

    assert run_quant._load_open_positions() is None
