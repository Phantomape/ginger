from __future__ import annotations

from datetime import date, timedelta

from quant.volatility_contraction_paper_sleeve import (
    RULE_VERSION,
    TOPN_CANDIDATE_RULE_VERSION,
    build_volatility_contraction_paper_sleeve_snapshot,
    empty_volatility_contraction_paper_state,
)


def _market_rows(start_price: float, step: float, *, days: int = 80) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = start_price + step * idx
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 0.995, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": 10_000_000,
            }
        )
    return rows


def _volatility_contraction_rows(
    *,
    base_price: float,
    signal_close: float,
    post_step: float,
    days: int = 80,
) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        if idx < 50:
            close = base_price + idx * 0.05
            high = close + 1.0
            low = close - 1.0
        elif idx < 60:
            close = base_price + 2.0 + (idx - 50) * 0.02
            high = close + 0.08
            low = close - 0.08
        elif idx == 60:
            close = signal_close
            high = signal_close + 0.10
            low = signal_close - 0.25
        else:
            close = signal_close + (idx - 60) * post_step
            high = close + 0.20
            low = close - 0.20
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 1.001, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": 1_200_000,
            }
        )
    return rows


def _snapshot(config: dict | None = None) -> dict:
    spy_rows = _market_rows(100.0, 0.05)
    qqq_rows = _market_rows(100.0, 0.25)
    aaa_rows = _volatility_contraction_rows(
        base_price=50.0,
        signal_close=54.0,
        post_step=0.25,
    )
    bbb_rows = _volatility_contraction_rows(
        base_price=70.0,
        signal_close=74.0,
        post_step=0.20,
    )
    as_of = aaa_rows[60]["date"]
    return build_volatility_contraction_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={
            "SPY": spy_rows,
            "QQQ": qqq_rows,
            "AAA": aaa_rows,
            "BBB": bbb_rows,
        },
        candidate_universe=["AAA", "BBB"],
        state=empty_volatility_contraction_paper_state(),
        config=config,
        persist=False,
    )


def test_default_adapter_emits_top2_pending_entries_without_orders():
    snapshot = _snapshot()

    assert snapshot["rule_version"] == RULE_VERSION
    assert snapshot["candidate_count"] == 2
    assert snapshot["new_pending_count"] == 2
    assert snapshot["pending_count"] == 2
    assert [row["vcp_candidate_rank_on_signal_date"] for row in snapshot["candidates"]] == [
        1,
        2,
    ]
    assert {row["topn_candidate_rule_version"] for row in snapshot["candidates"]} == {
        TOPN_CANDIDATE_RULE_VERSION
    }
    assert {row["max_paper_trades_per_day"] for row in snapshot["candidates"]} == {2}
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False


def test_daily_entry_slots_override_can_keep_top1_behavior():
    snapshot = _snapshot({"daily_entry_slots": 1})

    assert snapshot["candidate_count"] == 2
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["rejected_candidate_count"] == 1
    assert snapshot["rejected_candidates"][0]["reasons"] == [
        "daily_topn_or_capacity_limit"
    ]
    assert snapshot["candidates"][0]["max_paper_trades_per_day"] == 1
