from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from quant import reference_cache_refresh as rcr

NOW = datetime(2026, 6, 14, tzinfo=timezone.utc)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).replace(microsecond=0).isoformat()


def test_stale_sector_tickers_selects_oldest_and_missing_capped() -> None:
    entries = {
        "FRESH": {"sector": "Tech", "fetched_at": _iso(2)},
        "OLD1": {"sector": "Tech", "fetched_at": _iso(40)},
        "OLD2": {"sector": "Tech", "fetched_at": _iso(60)},
        # MISSING has no entry -> infinitely stale, must be picked first
    }
    picked = rcr.stale_sector_tickers(
        tickers=["FRESH", "OLD1", "OLD2", "MISSING", "BAD.TICK"],
        cache_entries=entries,
        now=NOW,
        stale_days=21,
        max_refresh=2,
    )
    assert picked == ["MISSING", "OLD2"]  # oldest-first, capped at 2, dotted ticker excluded


def test_refresh_sector_cache_rolling_only_builds_stale_slice() -> None:
    cache = {
        "entries": {
            "FRESH": {"sector": "Tech", "fetched_at": _iso(1)},
            "STALE": {"sector": "Tech", "fetched_at": _iso(99)},
        }
    }
    built: list[list[str]] = []

    def fake_build(tickers, *, path, skip_existing):
        built.append(list(tickers))
        assert skip_existing is False
        return {"entries": {}}

    result = rcr.refresh_sector_cache_rolling(
        tickers=["FRESH", "STALE", "NEWBIE"],
        now=NOW,
        load_fn=lambda path: cache,
        build_fn=fake_build,
        cache_path="ignored.json",
    )
    assert result["status"] == "refreshed"
    assert set(built[0]) == {"STALE", "NEWBIE"}  # FRESH skipped
    assert "FRESH" not in built[0]


def test_refresh_sector_cache_rolling_noop_when_all_fresh() -> None:
    cache = {"entries": {"A": {"sector": "X", "fetched_at": _iso(1)}}}
    calls = []
    result = rcr.refresh_sector_cache_rolling(
        tickers=["A"],
        now=NOW,
        load_fn=lambda path: cache,
        build_fn=lambda *a, **k: calls.append(1),
        cache_path="ignored.json",
    )
    assert result["status"] == "fresh"
    assert calls == []


def test_sec_company_tickers_throttle(tmp_path) -> None:
    cache = tmp_path / "sec_company_tickers.json"
    cache.write_text("{}", encoding="utf-8")
    import os

    # Make the file look 2 days old -> within 7-day TTL -> no refresh.
    old = (NOW - timedelta(days=2)).timestamp()
    os.utime(cache, (old, old))
    calls = []
    fresh = rcr.refresh_sec_company_tickers_if_due(
        now=NOW, refresh_fn=lambda p: calls.append(p), cache_path=cache
    )
    assert fresh["refreshed"] is False
    assert calls == []

    # Make it look 10 days old -> stale -> refresh fires.
    stale = (NOW - timedelta(days=10)).timestamp()
    os.utime(cache, (stale, stale))
    due = rcr.refresh_sec_company_tickers_if_due(
        now=NOW, refresh_fn=lambda p: calls.append(p), cache_path=cache
    )
    assert due["refreshed"] is True
    assert len(calls) == 1


def test_refresh_reference_caches_orchestrates_and_respects_env(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    sector_calls = []
    ticker_calls = []

    summary = rcr.refresh_reference_caches(
        universe=["AAA", "BBB"],
        now=NOW,
        env_get=lambda name, default=None: default,  # nothing disabled
        state_path=state_path,
        sector_refresh_fn=lambda **k: sector_calls.append(k) or {"status": "refreshed", "refreshed_count": 2},
        tickers_refresh_fn=lambda **k: ticker_calls.append(k) or {"status": "fresh", "refreshed": False},
    )
    assert summary["status"] == "completed"
    assert summary["sector_cache"]["refreshed_count"] == 2
    assert len(sector_calls) == 1 and len(ticker_calls) == 1
    assert json.loads(state_path.read_text(encoding="utf-8"))["rule_version"] == rcr.RULE_VERSION


def test_refresh_reference_caches_env_optouts(tmp_path) -> None:
    disabled = {"SECTOR_CACHE_REFRESH_DISABLED": "1"}
    sector_calls = []
    summary = rcr.refresh_reference_caches(
        universe=["AAA"],
        now=NOW,
        env_get=lambda name, default=None: disabled.get(name, default),
        state_path=tmp_path / "s.json",
        sector_refresh_fn=lambda **k: sector_calls.append(k) or {"status": "refreshed"},
        tickers_refresh_fn=lambda **k: {"status": "fresh"},
    )
    assert sector_calls == []  # sector disabled
    assert summary["sector_cache"]["status"] == "skipped"

    # Global kill-switch short-circuits everything.
    full_off = rcr.refresh_reference_caches(
        universe=["AAA"],
        now=NOW,
        env_get=lambda name, default=None: {"REFERENCE_CACHE_REFRESH_DISABLED": "true"}.get(name, default),
        state_path=tmp_path / "s2.json",
        sector_refresh_fn=lambda **k: sector_calls.append(k) or {},
        tickers_refresh_fn=lambda **k: {},
    )
    assert full_off["status"] == "disabled"
    assert sector_calls == []
