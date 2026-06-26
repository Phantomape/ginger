"""Offline tests for the advisory intraday risk review (no network)."""

from datetime import date

import pandas as pd

import intraday_quotes
import intraday_review
from intraday_review import (
    build_intraday_market_regime,
    build_position_reviews,
    intraday_output_path,
    render_intraday_report,
    split_completed_sessions,
)

ASOF = date(2026, 6, 10)
CAPTURE_TIME_ET = "2026-06-10 13:00 ET"


def _ohlcv(end="2026-06-09", days=30, base=100.0, spread=0.5, last_close=None):
    idx = pd.bdate_range(end=end, periods=days)
    closes = [base] * days
    if last_close is not None:
        closes[-1] = last_close
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + spread for c in closes],
            "Low": [c - spread for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * days,
        },
        index=idx,
    )


def _open_positions(**overrides):
    pos = {
        "ticker": "NVDA",
        "shares": 10,
        "avg_cost": 90.0,
        "entry_date": "2026-05-26",
        "override_stop_price": 95.0,
        "target_price": 120.0,
    }
    pos.update(overrides)
    return {"portfolio_value_usd": 100_000, "cash_usd": 50_000, "positions": [pos]}


def _quote(price, day_high=None, source="fast_info", capture_time_et=CAPTURE_TIME_ET):
    return {
        "ticker": "NVDA",
        "price": price,
        "day_high": day_high,
        "day_low": None,
        "source": source,
        "quote_time_et": None,
        "capture_time_et": capture_time_et,
        "is_stale": False,
    }


# ── split_completed_sessions ─────────────────────────────────────────────────

def test_split_excludes_todays_partial_bar():
    frame = _ohlcv(end="2026-06-10", days=10)  # last row IS the as-of date
    completed, partial = split_completed_sessions(frame, ASOF)
    assert partial is not None
    assert len(completed) == 9
    assert completed.index[-1].date() == date(2026, 6, 9)


def test_split_keeps_fully_completed_history():
    frame = _ohlcv(end="2026-06-09", days=10)  # ends yesterday
    completed, partial = split_completed_sessions(frame, ASOF)
    assert partial is None
    assert len(completed) == 10


def test_split_handles_empty_input():
    assert split_completed_sessions(None, ASOF) == (None, None)


# ── position re-check wiring (existing rules, intraday price) ────────────────

def test_intraday_price_below_override_stop_reports_hard_stop_breach():
    reviews = build_position_reviews(
        _open_positions(), {"NVDA": _ohlcv()}, {"NVDA": _quote(94.5)}, ASOF
    )
    (review,) = reviews
    assert review["status"] == "BREACHED"
    signals = review["context"]["exit_signals"]
    assert signals["critical_exit"] is True
    assert "HARD_STOP" in [r["rule"] for r in signals["triggered_rules"]]


def test_price_near_stop_sets_proximity_flag_without_triggering_rule():
    # 96.5 vs override stop 95.0 -> ~1.55% away: display flag only.
    reviews = build_position_reviews(
        _open_positions(), {"NVDA": _ohlcv()}, {"NVDA": _quote(96.5)}, ASOF
    )
    (review,) = reviews
    assert review["status"] == "APPROACHING"
    assert "NEAR_HARD_STOP" in review["proximity_flags"]
    assert review["context"]["exit_signals"]["any_triggered"] is False
    assert 0 < review["distance_to_hard_stop_pct"] < intraday_review.PROXIMITY_PCT


def test_price_well_above_stops_is_ok_with_session_return():
    reviews = build_position_reviews(
        _open_positions(), {"NVDA": _ohlcv()}, {"NVDA": _quote(101.0)}, ASOF
    )
    (review,) = reviews
    assert review["status"] == "OK"
    assert review["quote"]["capture_time_et"] == CAPTURE_TIME_ET
    assert review["proximity_flags"] == []
    # prev_close comes from the last COMPLETED session (100.0), not the quote.
    assert review["context"]["prev_close"] == 100.0
    assert review["context"]["daily_return_pct"] == 0.01


def test_partial_today_bar_does_not_poison_prev_close():
    # Frame includes today's unfinished bar at the intraday price itself; if it
    # leaked into prev_close, session return would be pinned to 0.
    frame = _ohlcv(end="2026-06-10", days=30, last_close=101.0)
    reviews = build_position_reviews(
        _open_positions(), {"NVDA": frame}, {"NVDA": _quote(101.0)}, ASOF
    )
    (review,) = reviews
    assert review["context"]["prev_close"] == 100.0
    assert review["context"]["daily_return_pct"] == 0.01


def test_quote_unavailable_is_flagged_not_silently_skipped():
    quote = {"ticker": "NVDA", "price": None, "source": "unavailable", "is_stale": True}
    reviews = build_position_reviews(
        _open_positions(), {"NVDA": _ohlcv()}, {"NVDA": quote}, ASOF
    )
    (review,) = reviews
    assert review["status"] == "QUOTE_UNAVAILABLE"
    report = render_intraday_report(_review_stub(positions=reviews))
    assert "QUOTE UNAVAILABLE" in report
    assert "manual check required" in report


# ── intraday market regime ───────────────────────────────────────────────────

def _index_frames():
    # Last completed closes above the short MA for both indices.
    return {
        "SPY": _ohlcv(end="2026-06-09", days=10, base=100.0, last_close=101.0),
        "QQQ": _ohlcv(end="2026-06-09", days=10, base=100.0, last_close=101.0),
    }


def test_regime_flip_intraday_flagged():
    quotes = {
        "SPY": {
            "price": 95.0,
            "source": "fast_info",
            "capture_time_et": CAPTURE_TIME_ET,
        },   # below MA intraday
        "QQQ": {
            "price": 105.0,
            "source": "fast_info",
            "capture_time_et": CAPTURE_TIME_ET,
        },  # still above
    }
    regime = build_intraday_market_regime(_index_frames(), quotes, ASOF, ma_period=5)
    assert regime["eod_basis_regime"] == "BULL"
    assert regime["regime"] == "NEUTRAL"
    assert regime["regime_flip_intraday"] is True
    assert regime["indices"]["SPY"]["eod_above_ma"] is True
    assert regime["indices"]["SPY"]["above_ma"] is False
    assert regime["indices"]["SPY"]["capture_time_et"] == CAPTURE_TIME_ET


def test_regime_no_flip_when_intraday_agrees():
    quotes = {
        "SPY": {"price": 105.0, "source": "fast_info"},
        "QQQ": {"price": 105.0, "source": "fast_info"},
    }
    regime = build_intraday_market_regime(_index_frames(), quotes, ASOF, ma_period=5)
    assert regime["regime"] == "BULL"
    assert regime["regime_flip_intraday"] is False


def test_regime_falls_back_to_eod_close_without_quotes():
    regime = build_intraday_market_regime(_index_frames(), {}, ASOF, ma_period=5)
    assert regime["regime"] == "BULL"
    assert regime["indices"]["SPY"]["price_source"] == "eod_close_fallback"


# ── quote fallback chain ─────────────────────────────────────────────────────

class _FakeFastInfo:
    def __init__(self, values=None, fail=False):
        self._values = values or {}
        self._fail = fail

    def __getitem__(self, key):
        if self._fail or key not in self._values:
            raise KeyError(key)
        return self._values[key]


class _FakeTicker:
    fast_info_values = None
    history_frame = None

    def __init__(self, ticker):
        self.ticker = ticker

    @property
    def fast_info(self):
        if self.fast_info_values is None:
            raise RuntimeError("fast_info down")
        return _FakeFastInfo(self.fast_info_values)

    def history(self, **kwargs):
        if self.history_frame is None:
            raise RuntimeError("history down")
        return self.history_frame


def test_quote_uses_fast_info_when_available(monkeypatch):
    _FakeTicker.fast_info_values = {
        "last_price": 50.0, "day_high": 51.0, "day_low": 49.0,
    }
    _FakeTicker.history_frame = None
    monkeypatch.setattr(intraday_quotes.yf, "Ticker", _FakeTicker)
    quote = intraday_quotes.get_intraday_quote(
        "NVDA",
        daily_close_fallback=42.0,
        capture_time_et=CAPTURE_TIME_ET,
    )
    assert quote["source"] == "fast_info"
    assert quote["price"] == 50.0
    assert quote["quote_time_et"] is None
    assert quote["capture_time_et"] == CAPTURE_TIME_ET
    assert quote["is_stale"] is False


def test_quote_falls_back_to_1m_bars(monkeypatch):
    _FakeTicker.fast_info_values = None
    idx = pd.date_range("2026-06-10 09:30", periods=3, freq="1min", tz="America/New_York")
    _FakeTicker.history_frame = pd.DataFrame(
        {"Open": [50, 50, 50], "High": [51, 52, 50.5], "Low": [49, 50, 50],
         "Close": [50.0, 51.0, 50.5], "Volume": [1, 1, 1]},
        index=idx,
    )
    monkeypatch.setattr(intraday_quotes.yf, "Ticker", _FakeTicker)
    quote = intraday_quotes.get_intraday_quote(
        "NVDA",
        daily_close_fallback=42.0,
        capture_time_et=CAPTURE_TIME_ET,
    )
    assert quote["source"] == "intraday_1m"
    assert quote["price"] == 50.5
    assert quote["day_high"] == 52.0
    assert quote["quote_time_et"] is not None
    assert quote["capture_time_et"] == CAPTURE_TIME_ET


def test_quote_falls_back_to_eod_close_then_unavailable(monkeypatch):
    _FakeTicker.fast_info_values = None
    _FakeTicker.history_frame = None
    monkeypatch.setattr(intraday_quotes.yf, "Ticker", _FakeTicker)

    quote = intraday_quotes.get_intraday_quote(
        "NVDA",
        daily_close_fallback=42.0,
        capture_time_et=CAPTURE_TIME_ET,
    )
    assert quote["source"] == "eod_close_fallback"
    assert quote["price"] == 42.0
    assert quote["capture_time_et"] == CAPTURE_TIME_ET
    assert quote["is_stale"] is True

    quote = intraday_quotes.get_intraday_quote(
        "NVDA",
        daily_close_fallback=None,
        capture_time_et=CAPTURE_TIME_ET,
    )
    assert quote["source"] == "unavailable"
    assert quote["price"] is None
    assert quote["capture_time_et"] == CAPTURE_TIME_ET


def test_batch_quotes_share_one_capture_time(monkeypatch):
    _FakeTicker.fast_info_values = {"last_price": 50.0}
    _FakeTicker.history_frame = None
    monkeypatch.setattr(intraday_quotes.yf, "Ticker", _FakeTicker)
    quotes = intraday_quotes.get_intraday_quotes(
        ["NVDA", "MSFT"],
        capture_time_et=CAPTURE_TIME_ET,
    )
    assert {q["capture_time_et"] for q in quotes.values()} == {CAPTURE_TIME_ET}


# ── report / output isolation ────────────────────────────────────────────────

def _review_stub(positions=()):
    return {
        "generated_at_et": "2026-06-10 13:00 ET",
        "generated_at_pt": "10:00 PT",
        "date": "20260610",
        "time_label": "1300ET",
        "macro": intraday_review.build_macro_context("2026-06-10"),
        "market_regime_intraday": {"regime": "BULL", "eod_basis_regime": "BULL",
                                   "regime_flip_intraday": False, "indices": {}},
        "portfolio_heat": None,
        "positions": list(positions),
        "pending_actions": [],
        "news": None,
        "data_quality": {"quote_sources": {}},
    }


def test_report_carries_advisory_banner_and_macro_day():
    report = render_intraday_report(_review_stub())
    assert "ADVISORY ONLY" in report
    assert "Does not modify EOD artifacts" in report
    # 2026-06-10 is an official CPI release day in the shared calendar.
    assert "MACRO EVENT DAY: *** CPI" in report


def test_output_paths_stay_inside_intraday_subtree(tmp_path):
    for kind in ("report", "llm_prompt", "news_raw", "trade_news", "snapshot"):
        path = intraday_output_path(kind, "20260610", "1300ET", tmp_path)
        rel = path.relative_to(tmp_path)
        assert rel.parts[:2] == ("daily", "intraday"), rel
        assert "20260610_1300ET" in path.name
    # Nothing may resolve into the EOD news/signals/report trees.
    assert not (tmp_path / "daily" / "news").exists()
    assert not (tmp_path / "daily" / "reports").exists()
