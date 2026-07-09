from __future__ import annotations

from datetime import date, timedelta

from quant.sec_item101_contract_relation_paper_sleeve import (
    RULE_VERSION,
    build_sec_item101_contract_relation_candidates,
    build_sec_item101_contract_relation_paper_sleeve_snapshot,
    empty_sec_item101_contract_relation_paper_state,
    replay_sec_item101_contract_relation_paper_trades,
)


def _weekdays(start: date, count: int) -> list[date]:
    out: list[date] = []
    cursor = start
    while len(out) < count:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


DATES = _weekdays(date(2026, 1, 5), 80)
ASOF_IDX = 60


def _asof() -> str:
    return DATES[ASOF_IDX].isoformat()


def _ohlcv_rows(base: float, step: float) -> list[dict]:
    rows = []
    for idx, day in enumerate(DATES):
        close = base + step * idx
        rows.append(
            {
                "date": day.isoformat(),
                "open": round(close * 0.995, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": 2_000_000,
            }
        )
    return rows


def _ohlcv() -> dict[str, list[dict]]:
    return {
        "SPY": _ohlcv_rows(100.0, 0.05),
        "BEST": _ohlcv_rows(80.0, 0.30),
        "OTHER": _ohlcv_rows(60.0, 0.10),
    }


def _relation_row(
    ticker: str,
    bucket: str,
    *,
    accession: str,
    evidence_count: int = 1,
    counterparty=True,
) -> dict:
    return {
        "schema_version": "sec_contract_relation_provenance_v1",
        "observer_name": "sec_contract_relation_provenance",
        "observer_only": True,
        "trade_enabled": False,
        "ticker": ticker,
        "accession_number": accession,
        "relation_bucket": bucket,
        "relation_quality": "specific_relation_phrase",
        "evidence_phrase_count": evidence_count,
        "counterparty_candidates": ["Acme LLC"] if counterparty else [],
        "usable_trade_date": _asof(),
        "accepted_at": _asof() + "T12:00:00",
        "filing_date": _asof(),
        "source_text_hash16": accession[-4:],
    }


def test_candidates_use_fixed_relation_priority_and_daily_top1():
    rows = [
        _relation_row("OTHER", "credit_or_financing_agreement", accession="0001"),
        _relation_row("BEST", "customer_or_revenue_contract", accession="0002"),
        _relation_row("BEST", "supplier_or_supply_contract", accession="0003"),
    ]

    candidates, rejects = build_sec_item101_contract_relation_candidates(
        relation_rows=rows,
        as_of=_asof(),
    )

    assert [row["ticker"] for row in candidates] == ["BEST"]
    assert candidates[0]["relation_bucket"] == "customer_or_revenue_contract"
    assert candidates[0]["rule_version"] == RULE_VERSION
    assert candidates[0]["trade_enabled"] is False
    assert candidates[0]["alters_orders"] is False
    assert rejects["daily_top1_limit"] == 2


def test_snapshot_admits_top1_pending_without_orders_and_is_idempotent():
    state = empty_sec_item101_contract_relation_paper_state()
    rows = [_relation_row("BEST", "customer_or_revenue_contract", accession="0002")]

    first = build_sec_item101_contract_relation_paper_sleeve_snapshot(
        as_of=_asof(),
        ohlcv_by_ticker=_ohlcv(),
        relation_rows=rows,
        state=state,
        persist=False,
    )

    assert first["trade_enabled"] is False
    assert first["new_pending_count"] == 1
    assert first["pending_entries"][0]["ticker"] == "BEST"
    assert first["production_impact"]["alters_orders"] is False

    carried = {
        "pending_entries": first["pending_entries"],
        "open_positions": first["open_positions"],
        "closed_positions": [],
        "skipped_entries": [],
    }
    second = build_sec_item101_contract_relation_paper_sleeve_snapshot(
        as_of=_asof(),
        ohlcv_by_ticker=_ohlcv(),
        relation_rows=rows,
        state=carried,
        persist=False,
    )

    assert second["new_pending_count"] == 0
    assert second["pending_count"] == 1


def test_pending_fills_next_session_and_closes_after_hold_days():
    rows = [_relation_row("BEST", "customer_or_revenue_contract", accession="0002")]
    state = empty_sec_item101_contract_relation_paper_state()
    snapshot = build_sec_item101_contract_relation_paper_sleeve_snapshot(
        as_of=_asof(),
        ohlcv_by_ticker=_ohlcv(),
        relation_rows=rows,
        state=state,
        persist=False,
    )
    state = {
        "pending_entries": snapshot["pending_entries"],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }

    filled_seen = False
    for idx in range(ASOF_IDX + 1, len(DATES)):
        step = build_sec_item101_contract_relation_paper_sleeve_snapshot(
            as_of=DATES[idx].isoformat(),
            ohlcv_by_ticker=_ohlcv(),
            relation_rows=[],
            state=state,
            persist=False,
        )
        if step.get("error"):
            continue
        filled_seen = filled_seen or bool(step["filled_count"])
        state = {
            "pending_entries": step["pending_entries"],
            "open_positions": step["open_positions"],
            "closed_positions": state["closed_positions"] + step["closed_positions_today"],
            "skipped_entries": [],
        }
        if state["closed_positions"]:
            break

    assert filled_seen is True
    assert len(state["closed_positions"]) == 1
    assert state["closed_positions"][0]["ticker"] == "BEST"
    assert state["closed_positions"][0]["trade_enabled"] is False


def test_replay_uses_same_top1_rule_and_costed_10_session_exit():
    rows = [
        _relation_row("OTHER", "credit_or_financing_agreement", accession="0001"),
        _relation_row("BEST", "customer_or_revenue_contract", accession="0002"),
    ]

    result = replay_sec_item101_contract_relation_paper_trades(
        ohlcv_by_ticker=_ohlcv(),
        relation_rows=rows,
        start=DATES[30].isoformat(),
        end=DATES[-1].isoformat(),
    )

    assert len(result["trades"]) == 1
    trade = result["trades"][0]
    assert trade["ticker"] == "BEST"
    assert trade["signal_date"] == _asof()
    assert trade["entry_date"] == _asof()
    assert trade["exit_date"] == DATES[ASOF_IDX + 9].isoformat()
    assert trade["trade_enabled"] is False
    assert trade["pnl"] > 0
