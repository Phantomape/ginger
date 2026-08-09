"""Focused integration guards for fresh-core entry admission.

The optional policy runs after signal qualification and actual fill-date
discovery.  These tests protect its three important boundaries: default-off
parity, delayed-fill semantics, and isolation from follow-through add-ons.
"""

import os
import sys

import pandas as pd
import pytest


sys.path.insert(0, os.path.dirname(__file__))

from backtester import BacktestEngine  # noqa: E402


_OMIT_POLICY = object()


class _RecordingAdmissionPolicy:
    metadata = {
        "policy": "unit_test_fresh_core_entry_admission_v1",
        "default_off": True,
    }

    def __init__(self, decide):
        self._decide = decide
        self.calls = []

    def evaluate(self, *, signal_date, ticker, fill_date):
        self.calls.append({
            "signal_date": signal_date,
            "ticker": ticker,
            "fill_date": fill_date,
        })
        admit = bool(self._decide(signal_date, ticker, fill_date))
        return {
            "admit": admit,
            "status": "admitted" if admit else "denied",
            "reason": "unit_test_allow" if admit else "unit_test_deny",
            "provenance": {
                "source": "unit_test",
                "signal_date_seen": signal_date,
                "fill_date_seen": fill_date,
            },
        }


def _price_frame(index, *, last_open=100.0, last_high=100.0, last_low=100.0):
    count = len(index)
    return pd.DataFrame({
        "Open": [100.0] * (count - 1) + [last_open],
        "High": [100.0] * (count - 1) + [last_high],
        "Low": [100.0] * (count - 1) + [last_low],
        "Close": [100.0] * (count - 1) + [last_open],
    }, index=index)


def _engine_harness(
    monkeypatch,
    ticker_frame,
    spy_frame,
    *,
    entry_admission_policy=_OMIT_POLICY,
    addon_enabled=False,
):
    """Build a deterministic one-signal engine around the real entry loop."""
    import backtester
    import feature_layer
    import portfolio_engine
    import regime as regime_mod
    import risk_engine
    import signal_engine

    monkeypatch.setattr(
        BacktestEngine,
        "_download_data",
        lambda self: {"TEST": ticker_frame, "SPY": spy_frame, "QQQ": spy_frame},
    )
    monkeypatch.setattr(
        BacktestEngine,
        "_download_earnings_calendar",
        lambda self: {},
    )
    monkeypatch.setattr(
        backtester,
        "build_coverage_report",
        lambda start, end, data_root=None: {
            "decision": "complete",
            "start": str(start),
            "end": str(end),
        },
    )
    monkeypatch.setattr(
        feature_layer,
        "compute_features",
        lambda ticker, frame, earnings: {
            "ticker": ticker,
            "close": float(frame["Close"].iloc[-1]),
            "atr": 1.0,
        },
    )
    monkeypatch.setattr(
        regime_mod,
        "compute_market_regime",
        lambda ohlcv_override=None: {
            "regime": "BULL",
            "indices": {
                "SPY": {"pct_from_ma": 0.05, "momentum_10d_pct": 0.02},
                "QQQ": {"pct_from_ma": 0.05},
            },
        },
    )
    emitted = {"value": False}

    def _one_signal(features, market_context=None, **kwargs):
        if emitted["value"] or "TEST" not in features:
            return []
        emitted["value"] = True
        return [{
            "ticker": "TEST",
            "strategy": "trend_long",
            "sector": "Tech",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "target_price": 110.0,
            "trade_quality_score": 0.8,
        }]

    monkeypatch.setattr(signal_engine, "generate_signals", _one_signal)
    monkeypatch.setattr(
        risk_engine,
        "enrich_signals",
        lambda signals, features, atr_target_mult=None: signals,
    )

    def _size(signals, equity, risk_pct=None):
        for signal in signals:
            signal["sizing"] = {"shares_to_buy": 10}
        return signals

    monkeypatch.setattr(portfolio_engine, "size_signals", _size)
    monkeypatch.setattr(
        portfolio_engine,
        "compute_portfolio_heat",
        lambda *args, **kwargs: None,
    )

    kwargs = {}
    if entry_admission_policy is not _OMIT_POLICY:
        kwargs["entry_admission_policy"] = entry_admission_policy
    engine = BacktestEngine(
        universe=["TEST"],
        config={
            "INITIAL_CAPITAL": 100_000,
            "MAX_POSITIONS": 5,
            "ADDON_ENABLED": addon_enabled,
        },
        include_oracle_diagnostics=False,
        **kwargs,
    )
    engine.start = spy_frame.index[0]
    engine.end = spy_frame.index[-1]
    return engine


def test_none_policy_preserves_exact_default_result(monkeypatch):
    index = pd.bdate_range("2025-10-01", periods=26)
    ticker_frame = _price_frame(index)
    spy_frame = ticker_frame.copy()

    default_result = _engine_harness(
        monkeypatch,
        ticker_frame,
        spy_frame,
    ).run()
    explicit_none_result = _engine_harness(
        monkeypatch,
        ticker_frame,
        spy_frame,
        entry_admission_policy=None,
    ).run()

    assert default_result == explicit_none_result
    assert "entry_admission" not in default_result


def test_policy_uses_actual_delayed_fill_date_and_denies_after_survival(
    monkeypatch,
):
    all_dates = pd.bdate_range("2025-10-01", periods=27)
    signal_date = all_dates[20]
    missing_next_session = all_dates[21]
    delayed_fill_date = all_dates[22]
    ticker_frame = _price_frame(all_dates).drop(index=missing_next_session)
    spy_frame = _price_frame(all_dates)
    policy = _RecordingAdmissionPolicy(lambda *_: False)

    result = _engine_harness(
        monkeypatch,
        ticker_frame,
        spy_frame,
        entry_admission_policy=policy,
    ).run()

    expected_call = {
        "signal_date": str(signal_date.date()),
        "ticker": "TEST",
        "fill_date": str(delayed_fill_date.date()),
    }
    assert policy.calls == [expected_call]
    assert result["signals_generated"] == 1
    assert result["signals_survived"] == 1
    assert result["total_trades"] == 0
    assert result["entry_execution_attribution"]["reason_counts"] == {
        "entry_admission_denied": 1,
    }
    audit = result["entry_admission"]
    assert audit["evaluated_count"] == 1
    assert audit["admitted_count"] == 0
    assert audit["denied_count"] == 1
    assert audit["status_counts"] == {"denied": 1}
    assert audit["reason_counts"] == {"unit_test_deny": 1}
    assert audit["events"] == [{
        "admit": False,
        "status": "denied",
        "reason": "unit_test_deny",
        "provenance": {
            "source": "unit_test",
            "signal_date_seen": str(signal_date.date()),
            "fill_date_seen": str(delayed_fill_date.date()),
        },
        **expected_call,
    }]


def test_policy_does_not_run_for_checkpoint_or_pending_addon(monkeypatch):
    index = pd.bdate_range("2025-10-01", periods=30)
    ticker_frame = _price_frame(
        index,
        last_open=112.0,
        last_high=113.0,
        last_low=112.0,
    )
    checkpoint_date = index[23]
    addon_fill_date = index[24]
    ticker_frame.loc[checkpoint_date, ["Open", "High", "Low", "Close"]] = [
        103.0,
        104.0,
        102.0,
        103.0,
    ]
    ticker_frame.loc[addon_fill_date, ["Open", "High", "Low", "Close"]] = [
        103.0,
        104.0,
        102.0,
        103.0,
    ]
    spy_frame = _price_frame(index)
    initial_fill_date = index[21]
    policy = _RecordingAdmissionPolicy(
        lambda signal_date, ticker, fill_date: (
            fill_date == str(initial_fill_date.date())
        )
    )

    result = _engine_harness(
        monkeypatch,
        ticker_frame,
        spy_frame,
        entry_admission_policy=policy,
        addon_enabled=True,
    ).run()

    assert policy.calls == [{
        "signal_date": str(index[20].date()),
        "ticker": "TEST",
        "fill_date": str(initial_fill_date.date()),
    }]
    assert result["entry_admission"]["evaluated_count"] == 1
    assert result["entry_admission"]["admitted_count"] == 1
    assert result["addon_attribution"]["scheduled"] == 1
    assert result["addon_attribution"]["executed"] == 1
    assert result["addon_attribution"]["skipped"] == 0
    assert result["trades"][0]["addon_count"] == 1


def test_policy_contract_fails_closed_at_construction_and_evaluation():
    class _MissingEvaluate:
        pass

    with pytest.raises(ValueError, match="must expose callable evaluate"):
        BacktestEngine(["TEST"], entry_admission_policy=_MissingEvaluate())

    class _MalformedResult:
        def evaluate(self, *, signal_date, ticker, fill_date):
            return {
                "admit": "yes",
                "status": "admitted",
                "reason": "wrong admit type",
                "provenance": {},
            }

    engine = BacktestEngine(["TEST"], entry_admission_policy=_MalformedResult())
    with pytest.raises(ValueError, match="admit must be bool"):
        engine._evaluate_entry_admission(
            signal_date="2025-10-01",
            ticker="test",
            fill_date="2025-10-02",
        )
