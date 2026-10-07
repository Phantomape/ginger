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


def _bars(prices: dict[str, tuple[float, float]]) -> dict:
    """Flat bars: every session same (open, close) per ticker."""
    bars = {
        ticker: {s: {"open": o, "close": c} for s in SESSIONS}
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
