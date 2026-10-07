"""Tests for the default-off dollar-neutral news-propagation pair sleeve.

Experiment: exp-20260827-001.
"""

from __future__ import annotations

import json

import pytest

import news_propagation_pair_paper_sleeve as sleeve


def _sessions(n: int) -> list[str]:
    # 12 weekday sessions starting 2026-08-03 (Mon), skipping weekends.
    from datetime import date, timedelta

    out = []
    day = date(2026, 8, 3)
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day.isoformat())
        day += timedelta(days=1)
    return out


SESSIONS = _sessions(14)


# exp-20260913-007: the five weekday sessions strictly before SESSIONS[0]
# (2026-07-27..2026-07-31) so admission-time priceability can be evaluated.
PRE_SESSIONS = [
    "2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31"
]


def _bars(
    prices: dict[str, tuple[float, float]], sessions: list[str] | None = None
) -> dict:
    """Flat bars: every session same (open, close) per ticker."""
    sessions = PRE_SESSIONS + (sessions or SESSIONS)
    bars = {
        ticker: {s: {"open": o, "close": c} for s in sessions}
        for ticker, (o, c) in prices.items()
    }
    bars["__splits__"] = {}
    return bars


def _ready_record(batch_id: str = "news-first-seen-testbatch0001") -> dict:
    return {
        "schema_version": sleeve.READINESS_SCHEMA_VERSION,
        "record_id": "pair-ready-test",
        "first_seen_batch_id": batch_id,
        # 23:07 ET Sunday 2026-08-02 -> entry session is Monday 2026-08-03.
        "first_seen_at": "2026-08-03T03:07:27+00:00",
        "status": "measurement_ready",
        "blockers": [],
        "long_side": {
            "row_count": 2,
            "ticker_row_counts": {"LNGA": 1, "LNGB": 1},
        },
        "short_side": {
            "row_count": 2,
            "ticker_row_counts": {"SHTA": 1, "SHTB": 1},
        },
        "borrow_coverage": {"required_tickers": 2, "covered_tickers": 2},
    }


def test_blocked_batch_never_admitted():
    record = _ready_record()
    record["status"] = "blocked"
    record["blockers"] = ["stale_pit_borrow:SHTA"]
    assert sleeve.build_news_propagation_pair_baskets([record]) == []


def test_admission_is_outcome_blind_and_default_off():
    record = _ready_record()
    # Outcome-shaped fields on the readiness record must not affect admission.
    record["net_pnl_usd"] = 999999.0
    record["realized_return"] = 9.9
    decisions = sleeve.build_news_propagation_pair_baskets([record])
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["trade_enabled"] is False
    assert decision["strategy_behavior_changed"] is False
    assert decision["signals"] == []
    assert decision["order_intents"] == []
    assert decision["orders"] == []
    assert decision["borrow_evidence"]["is_broker_locate"] is False
    assert decision["long_leg"]["weights"] == {"LNGA": 0.5, "LNGB": 0.5}
    assert decision["short_leg"]["weights"] == {"SHTA": 0.5, "SHTB": 0.5}


def test_settlement_dollar_neutral_math():
    decisions = sleeve.build_news_propagation_pair_baskets([_ready_record()])
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),  # +10%
            "LNGB": (100.0, 104.0),  # +4%
            "SHTA": (100.0, 102.0),  # +2%
            "SHTB": (100.0, 98.0),  # -2%
        }
    )
    outcome, blocker = sleeve.settle_pair_basket(decisions[0], bars)
    assert blocker is None
    assert outcome["entry_session"] == SESSIONS[0]
    assert outcome["exit_session"] == SESSIONS[9]
    # long +7% on $1000, short leg 0% on $1000, costs 2*45bp*$1000 = $9.
    assert outcome["long_leg_return"] == pytest.approx(0.07)
    assert outcome["short_leg_return"] == pytest.approx(0.0)
    assert outcome["gross_pnl_usd"] == pytest.approx(70.0)
    assert outcome["cost_usd"] == pytest.approx(9.0)
    assert outcome["net_pnl_usd"] == pytest.approx(61.0)
    assert outcome["trade_enabled"] is False


def test_missing_leg_bars_fail_closed():
    decisions = sleeve.build_news_propagation_pair_baskets([_ready_record()])
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            # SHTB missing entirely
        }
    )
    outcome, blocker = sleeve.settle_pair_basket(decisions[0], bars)
    assert outcome is None
    assert blocker == "missing_leg_bars:SHTB"


def test_incomplete_holding_window_stays_pending():
    record = _ready_record()
    record["first_seen_at"] = "2026-08-14T03:07:27+00:00"  # entry too late for H10
    decisions = sleeve.build_news_propagation_pair_baskets([record])
    bars = _bars({"SPY": (100.0, 101.0), "QQQ": (100.0, 100.0)})
    outcome, blocker = sleeve.settle_pair_basket(decisions[0], bars)
    assert outcome is None
    assert blocker == "holding_window_not_complete"


def test_run_is_idempotent_same_day(tmp_path):
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            "SHTB": (100.0, 98.0),
        }
    )
    records = [_ready_record()]
    first = sleeve.run(
        out_dir=tmp_path, readiness_records=records, bars=bars, now_utc="t0"
    )
    assert first["decisions"] == 1
    assert first["settled_baskets"] == 1
    assert first["appended_this_run"] == 2
    second = sleeve.run(
        out_dir=tmp_path, readiness_records=records, bars=bars, now_utc="t1"
    )
    assert second["decisions"] == 1
    assert second["settled_baskets"] == 1
    assert second["appended_this_run"] == 0
    rows = [
        json.loads(line)
        for line in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["trade_enabled"] is False


def test_replay_and_daily_share_admission_and_settlement(tmp_path):
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            "SHTB": (100.0, 98.0),
        }
    )
    records = [_ready_record()]
    replay = sleeve.build_news_propagation_pair_historical_trades(records, bars)
    daily = sleeve.run(
        out_dir=tmp_path, readiness_records=records, bars=bars, now_utc="t0"
    )
    assert replay["rule_version"] == daily["rule_version"] == sleeve.RULE_VERSION
    ledger = [
        json.loads(line)
        for line in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    daily_decision = next(r for r in ledger if r["record_type"] == "basket_decision")
    daily_outcome = next(r for r in ledger if r["record_type"] == "basket_outcome")
    assert replay["decisions"][0] == daily_decision
    assert replay["outcomes"][0] == daily_outcome


def test_acceptance_progress_reports_frozen_contract():
    progress = sleeve.acceptance_progress([])
    assert progress["contract"] == sleeve.ACCEPTANCE_CONTRACT
    assert progress["closed_baskets"] == 0
    assert progress["sample_sufficient"] is False


def test_split_normalization_on_massive_fallback_path():
    decisions = sleeve.build_news_propagation_pair_baskets([_ready_record()])
    bars = _bars(
        {
            "SPY": (100.0, 100.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 100.0),
            "LNGB": (100.0, 100.0),
            "SHTA": (100.0, 100.0),
            "SHTB": (100.0, 50.0),  # looks like -50%...
        }
    )
    # ...but a 2:1 split inside the window makes it flat.
    bars["__splits__"] = {"SHTB": [(SESSIONS[4], 2.0)]}
    outcome, blocker = sleeve.settle_pair_basket(decisions[0], bars)
    assert blocker is None
    assert outcome["short_leg_return"] == pytest.approx(0.0)
    assert outcome["net_pnl_usd"] == pytest.approx(-9.0)


def test_stale_warehouse_frame_falls_through_to_massive(tmp_path, monkeypatch):
    """exp-20260913-006: a warehouse frame that ends before the anchor's last
    warehouse bar must not shadow the massive_history fallback."""
    import sqlite3

    import pandas as pd

    import news_event_exposure_observer as observer

    def _frame(sessions: list[str]) -> pd.DataFrame:
        index = pd.to_datetime(sessions)
        return pd.DataFrame(
            {"Open": 100.0, "High": 100.0, "Low": 100.0, "Close": 100.0, "Volume": 1.0},
            index=index,
        )

    # SPY (anchor) current through the last session; STALE stops 8 sessions early.
    monkeypatch.setattr(
        observer,
        "load_frames",
        lambda tickers: {
            "SPY": _frame(SESSIONS),
            "QQQ": _frame(SESSIONS),
            "STALE": _frame(SESSIONS[:6]),
        },
    )
    db = tmp_path / "massive.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE daily_bars (ticker TEXT, trade_date TEXT, open REAL, close REAL)"
        )
        conn.execute(
            "CREATE TABLE stock_splits (ticker TEXT, execution_date TEXT, "
            "split_from REAL, split_to REAL)"
        )
        conn.executemany(
            "INSERT INTO daily_bars VALUES (?,?,?,?)",
            [("STALE", s, 100.0, 50.0) for s in SESSIONS],
        )
        conn.execute(
            "INSERT INTO stock_splits VALUES (?,?,?,?)", ("STALE", SESSIONS[4], 1.0, 2.0)
        )
    bars = sleeve.load_pair_bars({"STALE"}, massive_db=db)
    # Whole ticker comes from massive (all sessions, raw), with its splits.
    assert set(bars["STALE"]) == set(SESSIONS)
    assert bars["STALE"][SESSIONS[-1]] == {"open": 100.0, "close": 50.0}
    assert bars["__splits__"] == {"STALE": [(SESSIONS[4], 2.0)]}
    # Anchor and a current warehouse ticker are untouched.
    assert set(bars["SPY"]) == set(SESSIONS)
    assert "QQQ" in bars


def test_stale_warehouse_frame_kept_when_massive_is_not_fresher(tmp_path, monkeypatch):
    """exp-20261007-001: a stale-vs-anchor warehouse frame may still be newer
    than massive_history.  Keep the fresher warehouse rows instead of replacing
    them with an older fallback."""
    import sqlite3

    import pandas as pd

    import news_event_exposure_observer as observer

    def _frame(sessions: list[str]) -> pd.DataFrame:
        index = pd.to_datetime(sessions)
        return pd.DataFrame(
            {"Open": 100.0, "High": 100.0, "Low": 100.0, "Close": 100.0, "Volume": 1.0},
            index=index,
        )

    monkeypatch.setattr(
        observer,
        "load_frames",
        lambda tickers: {
            "SPY": _frame(SESSIONS),
            "QQQ": _frame(SESSIONS),
            "LAGGED": _frame(SESSIONS[:7]),
        },
    )
    db = tmp_path / "massive.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE daily_bars (ticker TEXT, trade_date TEXT, open REAL, close REAL)"
        )
        conn.execute(
            "CREATE TABLE stock_splits (ticker TEXT, execution_date TEXT, "
            "split_from REAL, split_to REAL)"
        )
        conn.executemany(
            "INSERT INTO daily_bars VALUES (?,?,?,?)",
            [("LAGGED", s, 100.0, 50.0) for s in SESSIONS[:6]],
        )
    bars = sleeve.load_pair_bars({"LAGGED"}, massive_db=db)
    assert set(bars["LAGGED"]) == set(SESSIONS[:7])
    assert bars["LAGGED"][SESSIONS[6]] == {"open": 100.0, "close": 100.0}
    assert bars["__splits__"] == {}


def test_unpriceable_ticker_excluded_at_admission_with_renormalized_weights():
    """exp-20260913-007: a ticker without a bar on every pre-entry lookback
    session is excluded at admission; weights renormalize; exclusion recorded."""
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            "SHTB": (100.0, 98.0),
        }
    )
    del bars["SHTB"][PRE_SESSIONS[2]]  # one missing pre-entry print
    decisions = sleeve.build_news_propagation_pair_baskets([_ready_record()], bars)
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["short_leg"]["weights"] == {"SHTA": 1.0}
    assert decision["short_leg"]["excluded_unpriceable"] == ["SHTB"]
    assert decision["long_leg"]["excluded_unpriceable"] == []
    assert decision["admission_priceability"]["sessions"] == PRE_SESSIONS
    assert decision["admission_priceability"]["rule_version"] == (
        sleeve.PRICEABILITY_RULE_VERSION
    )
    # Legacy path (no bars) keeps the frozen unfiltered behaviour.
    legacy = sleeve.build_pair_basket_decision(_ready_record())
    assert set(legacy["short_leg"]["weights"]) == {"SHTA", "SHTB"}
    assert "excluded_unpriceable" not in legacy["short_leg"]
    assert legacy["admission_priceability"] is None


def test_latest_session_lag_defers_admission_until_price_surface_catches_up(tmp_path):
    """exp-20261007-001: when the newest pre-entry session is the first-seen
    local date, a ticker with every prior lookback bar but no latest bar means
    the price surface is lagged.  Defer instead of consuming the batch with a
    transient excluded_unpriceable label."""
    record = _ready_record()
    record["first_seen_at"] = "2026-08-01T03:07:27+00:00"  # 2026-07-31 23:07 ET
    record["short_side"] = {
        "row_count": 3,
        "ticker_row_counts": {"SHTA": 1, "SHTB": 1, "SHTC": 1},
    }
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            "SHTB": (100.0, 98.0),
            "SHTC": (100.0, 97.0),
        }
    )
    del bars["SHTB"][PRE_SESSIONS[-1]]
    del bars["SHTC"][PRE_SESSIONS[-1]]

    assert sleeve.build_news_propagation_pair_baskets([record], bars) == []
    daily = sleeve.run(out_dir=tmp_path, readiness_records=[record], bars=bars, now_utc="t0")
    assert daily["appended_this_run"] == 0
    assert daily["decisions"] == 0
    assert not (tmp_path / "ledger.jsonl").exists()

    bars["SHTB"][PRE_SESSIONS[-1]] = {"open": 100.0, "close": 98.0}
    bars["SHTC"][PRE_SESSIONS[-1]] = {"open": 100.0, "close": 97.0}
    decisions = sleeve.build_news_propagation_pair_baskets([record], bars)
    assert len(decisions) == 1
    assert decisions[0]["short_leg"]["weights"] == {
        "SHTA": pytest.approx(1 / 3),
        "SHTB": pytest.approx(1 / 3),
        "SHTC": pytest.approx(1 / 3),
    }


def test_side_emptied_by_priceability_is_not_admitted():
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            # SHTA / SHTB have no bars anywhere -> short side empties.
        }
    )
    assert sleeve.build_news_propagation_pair_baskets([_ready_record()], bars) == []
    # Calendar too short for the lookback -> fail closed as well.
    short_calendar = {
        ticker: {s: row for s, row in rows.items() if s >= SESSIONS[0]}
        for ticker, rows in _bars(
            {"SPY": (100.0, 101.0), "QQQ": (100.0, 100.0), "LNGA": (100.0, 110.0),
             "LNGB": (100.0, 104.0), "SHTA": (100.0, 102.0), "SHTB": (100.0, 98.0)}
        ).items()
        if ticker != "__splits__"
    }
    short_calendar["__splits__"] = {}
    assert sleeve.build_news_propagation_pair_baskets([_ready_record()], short_calendar) == []


def test_unsettleable_only_after_grace_period():
    """A frozen (unfiltered) decision whose leg never gets a bar stays
    missing_leg_bars until GRACE sessions after exit, then terminalizes with
    no PnL fields and stays out of the acceptance contract."""
    decision = sleeve.build_pair_basket_decision(_ready_record())  # legacy, unfiltered
    prices = {
        "SPY": (100.0, 101.0),
        "QQQ": (100.0, 100.0),
        "LNGA": (100.0, 110.0),
        "LNGB": (100.0, 104.0),
        "SHTA": (100.0, 102.0),
        # SHTB missing everywhere
    }
    # exit = SESSIONS[9]; 14 sessions -> only 4 after exit -> still pending.
    outcome, blocker = sleeve.settle_pair_basket(decision, _bars(prices, _sessions(14)))
    assert outcome is None and blocker == "missing_leg_bars:SHTB"
    # 15 sessions -> 5 after exit -> unsettleable terminal row.
    outcome, blocker = sleeve.settle_pair_basket(decision, _bars(prices, _sessions(15)))
    assert blocker is None
    assert outcome["outcome_status"] == "unsettleable"
    assert outcome["unpriceable_legs"] == {"short_leg": ["SHTB"]}
    assert outcome["record_id"] == f"outcome:{decision['basket_id']}:10"
    assert not any(k.endswith("_usd") or k.endswith("_return") for k in outcome)
    progress = sleeve.acceptance_progress([outcome])
    assert progress["closed_baskets"] == 0
    # Daily path: the frozen pending decision is terminalized append-only.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "ledger.jsonl").write_text(
            json.dumps(decision, sort_keys=True) + "\n", encoding="utf-8"
        )
        summary = sleeve.run(
            out_dir=base, readiness_records=[], bars=_bars(prices, _sessions(15)), now_utc="t0"
        )
        assert summary["unsettleable_baskets"] == 1
        assert summary["settled_baskets"] == 0
        assert summary["pending_baskets"] == 0
        assert summary["acceptance_progress"]["closed_baskets"] == 0
        rows = [
            json.loads(line)
            for line in (base / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert [r["record_type"] for r in rows] == ["basket_decision", "basket_outcome"]
        assert rows[0] == decision  # frozen decision bytes unchanged


def test_daily_run_applies_priceability_at_admission(tmp_path):
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            "SHTB": (100.0, 98.0),
        }
    )
    del bars["LNGB"][PRE_SESSIONS[0]]
    records = [_ready_record()]
    daily = sleeve.run(out_dir=tmp_path, readiness_records=records, bars=bars, now_utc="t0")
    replay = sleeve.build_news_propagation_pair_historical_trades(records, bars)
    ledger = [
        json.loads(line)
        for line in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    decision = next(r for r in ledger if r["record_type"] == "basket_decision")
    assert decision["long_leg"]["weights"] == {"LNGA": 1.0}
    assert decision["long_leg"]["excluded_unpriceable"] == ["LNGB"]
    assert replay["decisions"][0] == decision
    assert daily["settled_baskets"] == replay["settled_baskets"] == 1
    assert daily["unsettleable_baskets"] == replay["unsettleable_baskets"] == 0


def _v2_record(uncovered: list[dict] | None = None) -> dict:
    """exp-20260923-004: readiness record carrying the v2 borrow-coverage keys."""
    record = _ready_record()
    uncovered = list(uncovered or [])
    record["borrow_coverage"] = {
        "required_tickers": 2,
        "covered_tickers": 2 - len(uncovered),
        "coverage_rule_version": "news_propagation_pair_borrow_coverage_v2",
        "uncovered_tickers": uncovered,
    }
    return record


def test_uncovered_short_ticker_excluded_at_admission_separately_from_priceability():
    """exp-20260923-004: short tickers the v2 readiness record lists without
    PIT borrow evidence are excluded (recorded apart from priceability), the
    equal row weights renormalize, and a v1 record is byte-identical."""
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            "SHTB": (100.0, 98.0),
        }
    )
    record = _v2_record([{"ticker": "SHTB", "blocker": "missing_pit_borrow"}])
    decisions = sleeve.build_news_propagation_pair_baskets([record], bars)
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["short_leg"]["weights"] == {"SHTA": 1.0}
    assert decision["short_leg"]["excluded_no_pit_borrow"] == ["SHTB"]
    assert decision["short_leg"]["excluded_unpriceable"] == []
    assert decision["long_leg"]["weights"] == {"LNGA": 0.5, "LNGB": 0.5}
    assert "excluded_no_pit_borrow" not in decision["long_leg"]
    assert decision["borrow_evidence"]["uncovered_tickers"] == 1
    assert decision["borrow_evidence"]["coverage_rule_version"] == (
        "news_propagation_pair_borrow_coverage_v2"
    )
    assert decision["borrow_evidence"]["is_broker_locate"] is False

    # No-bars path excludes as well, without a priceability label.
    legacy = sleeve.build_pair_basket_decision(record)
    assert legacy["short_leg"]["weights"] == {"SHTA": 1.0}
    assert legacy["short_leg"]["excluded_no_pit_borrow"] == ["SHTB"]
    assert "excluded_unpriceable" not in legacy["short_leg"]

    # Both labels coexist when a kept ticker is also unpriceable.
    partial = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            "SHTB": (100.0, 98.0),
            "SHTC": (100.0, 97.0),
        }
    )
    del partial["SHTA"][PRE_SESSIONS[0]]
    three = _v2_record([{"ticker": "SHTB", "blocker": "stale_pit_borrow"}])
    three["short_side"] = {
        "row_count": 3,
        "ticker_row_counts": {"SHTA": 1, "SHTB": 1, "SHTC": 1},
    }
    decision = sleeve.build_news_propagation_pair_baskets([three], partial)[0]
    assert decision["short_leg"]["weights"] == {"SHTC": 1.0}
    assert decision["short_leg"]["excluded_unpriceable"] == ["SHTA"]
    assert decision["short_leg"]["excluded_no_pit_borrow"] == ["SHTB"]

    # Short side emptied by the exclusion -> not admitted.
    empty = _v2_record(
        [
            {"ticker": "SHTA", "blocker": "missing_pit_borrow"},
            {"ticker": "SHTB", "blocker": "missing_pit_borrow"},
        ]
    )
    assert sleeve.build_news_propagation_pair_baskets([empty], bars) == []

    # v1 record (no uncovered key) keeps the frozen decision shape.
    plain = sleeve.build_pair_basket_decision(_ready_record(), bars)
    assert "excluded_no_pit_borrow" not in plain["short_leg"]
    assert set(plain["borrow_evidence"]) == {
        "required_tickers",
        "covered_tickers",
        "is_broker_locate",
        "source",
    }


def _overlap_record(excluded: list[str], uncovered: list[dict] | None = None) -> dict:
    """exp-20260924-004: readiness record carrying overlap_exclusion; BOTH sits
    on both sides of the batch."""
    record = _v2_record(uncovered)
    record["long_side"] = {
        "row_count": 3,
        "ticker_row_counts": {"BOTH": 1, "LNGA": 1, "LNGB": 1},
    }
    record["short_side"] = {
        "row_count": 3,
        "ticker_row_counts": {"BOTH": 1, "SHTA": 1, "SHTB": 1},
    }
    record["cross_side_ticker_overlap"] = ["BOTH"]
    record["overlap_exclusion"] = {
        "rule_version": "news_propagation_pair_cross_side_overlap_exclusion_v2",
        "excluded_tickers": list(excluded),
        "long_side_residual": {"ticker_count": 2, "row_count": 2, "max_ticker_row_weight": 0.5},
        "short_side_residual": {"ticker_count": 2, "row_count": 2, "max_ticker_row_weight": 0.5},
    }
    return record


def test_overlap_ticker_excluded_from_both_legs_at_admission():
    """exp-20260924-004: tickers listed in overlap_exclusion leave BOTH legs
    with renormalized equal weights and an independent label; a record without
    the key is byte-identical."""
    bars = _bars(
        {
            "SPY": (100.0, 101.0),
            "QQQ": (100.0, 100.0),
            "BOTH": (100.0, 100.0),
            "LNGA": (100.0, 110.0),
            "LNGB": (100.0, 104.0),
            "SHTA": (100.0, 102.0),
            "SHTB": (100.0, 98.0),
        }
    )
    decisions = sleeve.build_news_propagation_pair_baskets([_overlap_record(["BOTH"])], bars)
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["long_leg"]["weights"] == {"LNGA": 0.5, "LNGB": 0.5}
    assert decision["short_leg"]["weights"] == {"SHTA": 0.5, "SHTB": 0.5}
    assert decision["long_leg"]["excluded_cross_side_overlap"] == ["BOTH"]
    assert decision["short_leg"]["excluded_cross_side_overlap"] == ["BOTH"]
    assert decision["long_leg"]["excluded_unpriceable"] == []
    assert decision["short_leg"]["excluded_unpriceable"] == []
    # exp-20260923-004 label appears only when the record lists uncovered tickers.
    assert "excluded_no_pit_borrow" not in decision["short_leg"]
    assert "excluded_no_pit_borrow" not in decision["long_leg"]
    assert decision["overlap_exclusion"] == {
        "rule_version": "news_propagation_pair_cross_side_overlap_exclusion_v2",
        "excluded_tickers": 1,
    }

    # No-bars path excludes as well, without a priceability label.
    legacy = sleeve.build_pair_basket_decision(_overlap_record(["BOTH"]))
    assert legacy["long_leg"]["weights"] == {"LNGA": 0.5, "LNGB": 0.5}
    assert legacy["long_leg"]["excluded_cross_side_overlap"] == ["BOTH"]
    assert "excluded_unpriceable" not in legacy["long_leg"]

    # Labels stay independent: overlap + uncovered + unpriceable on the short leg.
    partial = {k: dict(v) for k, v in bars.items()}
    partial["SHTA"] = dict(bars["SHTA"])
    del partial["SHTA"][PRE_SESSIONS[0]]
    record = _overlap_record(["BOTH"], [{"ticker": "SHTB", "blocker": "missing_pit_borrow"}])
    record["short_side"]["ticker_row_counts"]["SHTC"] = 1
    record["short_side"]["row_count"] = 4
    partial["SHTC"] = {s: {"open": 100.0, "close": 97.0} for s in PRE_SESSIONS + SESSIONS}
    decision = sleeve.build_news_propagation_pair_baskets([record], partial)[0]
    assert decision["short_leg"]["weights"] == {"SHTC": 1.0}
    assert decision["short_leg"]["excluded_cross_side_overlap"] == ["BOTH"]
    assert decision["short_leg"]["excluded_no_pit_borrow"] == ["SHTB"]
    assert decision["short_leg"]["excluded_unpriceable"] == ["SHTA"]

    # A side emptied by the overlap exclusion is not admitted.
    empty = _overlap_record(["BOTH", "LNGA", "LNGB"])
    assert sleeve.build_news_propagation_pair_baskets([empty], bars) == []

    # Empty exclusion list (post-effective batch without overlap) keeps full legs
    # and records the empty label.
    none = _overlap_record([])
    decision = sleeve.build_pair_basket_decision(none, bars)
    assert set(decision["long_leg"]["weights"]) == {"BOTH", "LNGA", "LNGB"}
    assert decision["long_leg"]["excluded_cross_side_overlap"] == []
    assert decision["overlap_exclusion"]["excluded_tickers"] == 0

    # v2/v1 records (no overlap_exclusion key) keep the frozen decision shape.
    plain = sleeve.build_pair_basket_decision(_v2_record(), bars)
    assert "excluded_cross_side_overlap" not in plain["long_leg"]
    assert "excluded_cross_side_overlap" not in plain["short_leg"]
    assert "overlap_exclusion" not in plain
    v1 = sleeve.build_pair_basket_decision(_ready_record(), bars)
    assert "overlap_exclusion" not in v1
    assert set(v1["borrow_evidence"]) == {
        "required_tickers",
        "covered_tickers",
        "is_broker_locate",
        "source",
    }


def test_unsettleable_grace_waits_for_lagging_massive_source():
    """exp-20261007-002: the grace period is measured on the authorized price
    sources.  When the session anchor already shows 7 sessions past exit but
    massive_history has not yet published the grace session, a missing leg
    stays an ordinary blocker; once massive reaches the grace session the
    basket terminalizes exactly as before."""
    decision = sleeve.build_pair_basket_decision(_ready_record())  # legacy, unfiltered
    prices = {
        "SPY": (100.0, 101.0),
        "QQQ": (100.0, 100.0),
        "LNGA": (100.0, 110.0),
        "LNGB": (100.0, 104.0),
        "SHTA": (100.0, 102.0),
        # SHTB missing everywhere
    }
    sessions = _sessions(17)  # exit = SESSIONS[9]; 7 anchor sessions after exit
    grace_session = sessions[9 + sleeve.UNSETTLEABLE_GRACE_SESSIONS]
    bars = _bars(prices, sessions)
    bars["__source_last_sessions__"] = {
        "warehouse_anchor": sessions[-1],
        "massive": sessions[9 + sleeve.UNSETTLEABLE_GRACE_SESSIONS - 1],
    }
    outcome, blocker = sleeve.settle_pair_basket(decision, bars)
    assert outcome is None and blocker == "missing_leg_bars:SHTB"
    bars["__source_last_sessions__"]["massive"] = grace_session
    outcome, blocker = sleeve.settle_pair_basket(decision, bars)
    assert blocker is None
    assert outcome["outcome_status"] == "unsettleable"
    assert outcome["unpriceable_legs"] == {"short_leg": ["SHTB"]}
    assert not any(k.endswith("_usd") or k.endswith("_return") for k in outcome)
    # No massive source recorded (replay callers, legacy fixtures): anchor-only rule.
    bars["__source_last_sessions__"] = {"warehouse_anchor": sessions[-1], "massive": None}
    outcome, _ = sleeve.settle_pair_basket(decision, bars)
    assert outcome["outcome_status"] == "unsettleable"
