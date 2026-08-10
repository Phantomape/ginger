from __future__ import annotations

import json
from datetime import date, timedelta

from quant.core_drawdown_flow_put_stabilization_paper_sleeve import (
    FLOW_PIT_CONTRACT_VERSION,
    RULE_VERSION,
    build_core_drawdown_flow_put_candidates,
    build_core_drawdown_flow_put_snapshot,
    empty_core_drawdown_flow_put_state,
    load_option_chain_snapshot,
    replay_core_drawdown_flow_put_sleeve,
)
from quant.moomoo_capital_flow_paper_sleeve import flow_rows_by_ticker
from quant.us_market_calendar import is_us_equity_session


def _sessions(start: date, count: int) -> list[date]:
    result: list[date] = []
    cursor = start
    while len(result) < count:
        if is_us_equity_session(cursor):
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


DATES = _sessions(date(2026, 1, 2), 95)
ASOF_INDEX = 70


def _ticker_rows(offset: float = 0.0) -> list[dict]:
    closes: list[float] = []
    for index in range(len(DATES)):
        if index < ASOF_INDEX:
            closes.append(100.0 + offset - 0.30 * index)
        elif index == ASOF_INDEX:
            closes.append(80.5 + offset)
        else:
            closes.append(80.5 + offset + 0.35 * (index - ASOF_INDEX))
    rows = []
    for day, close in zip(DATES, closes):
        rows.append(
            {
                "date": day.isoformat(),
                "open": round(close - 0.10, 4),
                "high": round(close + 0.50, 4),
                "low": round(close - 1.00, 4),
                "close": round(close, 4),
                "volume": 2_000_000.0,
            }
        )
    return rows


def _ohlcv() -> dict[str, list[dict]]:
    spy = []
    for index, day in enumerate(DATES):
        close = 100.0 + 0.05 * index
        spy.append(
            {
                "date": day.isoformat(),
                "open": close - 0.05,
                "high": close + 0.4,
                "low": close - 0.4,
                "close": close,
                "volume": 4_000_000.0,
            }
        )
    return {"SPY": spy, "AAA": _ticker_rows(), "BBB": _ticker_rows(2.0)}


def _asof() -> str:
    return DATES[ASOF_INDEX].isoformat()


def _entry_date() -> str:
    return DATES[ASOF_INDEX + 1].isoformat()


def _flow_rows(as_of: str) -> list[dict]:
    return [
        {
            "ticker": "AAA",
            "flow_date": as_of,
            "main_in_flow": 30_000_000.0,
            "fetched_at": "2026-07-22T23:00:00Z",
        },
        {
            "ticker": "BBB",
            "flow_date": as_of,
            "main_in_flow": 5_000_000.0,
            "fetched_at": "2026-07-22T23:00:00Z",
        },
    ]


def _chain(*, near_oi: float, far_oi: float) -> dict:
    put_rows = []
    for _ in range(6):
        put_rows.append((80.0, near_oi))
        put_rows.append((65.0, far_oi))
    return {
        "captured_rows": 12,
        "liquid_rows": 12,
        "expiries": {"2026-05-15", "2026-05-22"},
        "put_rows": put_rows,
        "usable_trade_dates": {_entry_date()},
        "retrieved_ats": {"2026-05-14T22:00:00Z"},
        "pit_safe_rows": 12,
    }


def _option_state() -> dict[str, dict]:
    return {
        "AAA": _chain(near_oi=100.0, far_oi=10.0),
        "BBB": _chain(near_oi=20.0, far_oi=100.0),
    }


def _write_options(tmp_path, as_of: str, tickers=("AAA", "BBB")):
    chain_path = tmp_path / f"options_onclickmedia_chain_{as_of.replace('-', '')}.jsonl"
    rows = []
    for ticker in tickers:
        for expiry in ("2026-05-15", "2026-05-22"):
            for strike, oi in ((65.0, 10 if ticker == "AAA" else 100),
                               (78.0, 100 if ticker == "AAA" else 20),
                               (80.0, 100 if ticker == "AAA" else 20),
                               (81.0, 100 if ticker == "AAA" else 20),
                               (82.0, 100 if ticker == "AAA" else 20),
                               (83.0, 100 if ticker == "AAA" else 20)):
                rows.append(
                    {
                        "ticker": ticker,
                        "quote_date": as_of,
                        "date": as_of,
                        "expiration": expiry,
                        "call_put": "put",
                        "strike": strike,
                        "open_interest": oi,
                        "option_liquidity_pass": True,
                        "pit_safe": True,
                        "usable_trade_date": _entry_date(),
                        "retrieved_at": f"{as_of}T22:00:00Z",
                    }
                )
    chain_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    quality_path = tmp_path / "quality.json"
    quality_path.write_text(
        json.dumps(
            {
                "by_quote_date": {
                    as_of: {"status": "usable_for_shadow", "scoring_allowed": True}
                }
            }
        ),
        encoding="utf-8",
    )
    return chain_path, quality_path


def test_shared_selector_applies_full_rule_and_emits_signal_contract_fields():
    ohlcv = _ohlcv()
    as_of = _asof()
    candidates, rejects, stages = build_core_drawdown_flow_put_candidates(
        rows_by_ticker=ohlcv,
        flow_by_ticker=flow_rows_by_ticker(_flow_rows(as_of)),
        option_by_ticker=_option_state(),
        tickers=["AAA", "BBB"],
        as_of=as_of,
        options_scoring_allowed=True,
    )
    assert [row["ticker"] for row in candidates] == ["AAA", "BBB"]
    assert candidates[0]["rule_version"] == RULE_VERSION
    assert candidates[0]["entry_date"] == _entry_date()
    assert candidates[0]["target_price"] > candidates[0]["close"]
    assert candidates[0]["flow_pit_contract"] == FLOW_PIT_CONTRACT_VERSION
    assert candidates[0]["score"] > candidates[1]["score"]
    assert candidates[0]["trade_enabled"] is False
    assert candidates[0]["alters_orders"] is False
    assert stages["deep_drawdown_distress"] == 2
    assert stages["price_stabilized"] == 2
    assert stages["options_complete"] == 2
    assert rejects == {}


def test_selector_fails_closed_when_put_snapshot_is_missing():
    as_of = _asof()
    candidates, rejects, stages = build_core_drawdown_flow_put_candidates(
        rows_by_ticker=_ohlcv(),
        flow_by_ticker=flow_rows_by_ticker(_flow_rows(as_of)),
        option_by_ticker={},
        tickers=["AAA", "BBB"],
        as_of=as_of,
        options_scoring_allowed=True,
    )
    assert candidates == []
    assert rejects["missing_options_row_asof"] == 2
    assert stages["price_stabilized"] == 2
    assert stages["options_complete"] == 0


def test_exact_option_date_loader_and_daily_snapshot_share_the_selector(tmp_path):
    as_of = _asof()
    _, quality_path = _write_options(tmp_path, as_of)
    loaded, meta = load_option_chain_snapshot(as_of, options_dir=tmp_path)
    assert meta["status"] == "loaded"
    assert set(loaded) == {"AAA", "BBB"}
    assert len(loaded["AAA"]["expiries"]) == 2

    snapshot = build_core_drawdown_flow_put_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=_ohlcv(),
        flow_rows=_flow_rows(as_of),
        candidate_universe=["AAA", "BBB"],
        state=empty_core_drawdown_flow_put_state(),
        options_dir=tmp_path,
        options_quality_path=quality_path,
        persist=False,
    )
    assert snapshot["raw_candidate_count"] == 2
    assert snapshot["new_pending_count"] == 1
    assert snapshot["new_pending_entries"][0]["ticker"] == "AAA"
    assert snapshot["new_pending_entries"][0]["entry_date"] == _entry_date()
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False


def test_daily_state_fills_exact_next_open_and_closes_at_h10(tmp_path):
    as_of = _asof()
    _, quality_path = _write_options(tmp_path, as_of, tickers=("AAA",))
    first = build_core_drawdown_flow_put_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=_ohlcv(),
        flow_rows=[_flow_rows(as_of)[0]],
        candidate_universe=["AAA"],
        state=empty_core_drawdown_flow_put_state(),
        options_dir=tmp_path,
        options_quality_path=quality_path,
        persist=False,
    )
    state = {
        "pending_entries": first["pending_entries"],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }
    closed = []
    for day in DATES[ASOF_INDEX + 1 : ASOF_INDEX + 13]:
        step = build_core_drawdown_flow_put_snapshot(
            as_of=day.isoformat(),
            ohlcv_by_ticker=_ohlcv(),
            flow_rows=[],
            candidate_universe=["AAA"],
            state=state,
            options_dir=tmp_path,
            options_quality_path=quality_path,
            persist=False,
        )
        closed.extend(step["closed_positions_today"])
        state = {
            "pending_entries": step["pending_entries"],
            "open_positions": step["open_positions"],
            "closed_positions": closed,
            "skipped_entries": [],
        }
        if closed:
            break
    assert len(closed) == 1
    assert closed[0]["entry_date"] == _entry_date()
    assert closed[0]["exit_date"] == DATES[ASOF_INDEX + 11].isoformat()
    assert closed[0]["observed_trading_days"] == 10
    assert closed[0]["trade_enabled"] is False


def test_replay_reports_canonical_style_fail_closed_coverage_without_options(tmp_path):
    result = replay_core_drawdown_flow_put_sleeve(
        ohlcv_by_ticker=_ohlcv(),
        flow_rows=_flow_rows(_asof()),
        start=DATES[55].isoformat(),
        end=DATES[-1].isoformat(),
        tickers=["AAA", "BBB"],
        options_dir=tmp_path,
        options_quality_path=tmp_path / "missing-quality.json",
    )
    assert result["evidence_status"] == "blocked_no_options_history"
    assert result["metrics"]["signals_generated"] > 0
    assert result["metrics"]["signals_survived"] == 0
    assert result["metrics"]["survival_rate"] == 0.0
    assert result["metrics"]["trade_count"] == 0
    assert result["gate_checks"]["gate3_survival_at_least_5pct"] is False
    assert result["gate_checks"]["gate4_eligible"] is False
