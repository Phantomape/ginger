from __future__ import annotations

from datetime import date, timedelta

import pytest

from quant import fdic_call_report_deposit_repair_paper_sleeve as sleeve


def _row(
    *,
    quarter: str,
    ticker: str = "BANK",
    bank_id: str = "100",
    parent_group_id: str | None = None,
    bank_assets: float = 12_000_000.0,
    parent_assets: float = 14_000_000.0,
    core_deposits: float = 7_000_000.0,
    uninsured_deposits: float = 1_400_000.0,
    domestic_deposits: float = 10_000_000.0,
    all_office_deposits: float | None = None,
    release_date: str = "1900-01-01",
) -> dict:
    row = {
        "quarter": quarter,
        "ticker": ticker,
        "CERT": bank_id,
        "NAME": f"{ticker} Bank",
        "ASSET": bank_assets,
        "parent_group_assets_thousands": parent_assets,
        "COREDEP": core_deposits,
        "DEPUNINS": uninsured_deposits,
        "DEPDOM": domestic_deposits,
        # DEP intentionally remains a separate, non-canonical all-office
        # measure.  The helper must never use it as the DEPUNINS denominator.
        "DEP": all_office_deposits or domestic_deposits,
        # Deliberately bogus: the helper must use only its official release map.
        "release_date": release_date,
    }
    if parent_group_id is not None:
        row["RSSDHCR"] = parent_group_id
    return row


def _pair(
    *,
    quarter: str = "2024Q3",
    ticker: str = "BANK",
    bank_id: str = "100",
    parent_group_id: str | None = None,
    current_assets: float = 12_000_000.0,
    prior_assets: float = 10_000_000.0,
    parent_assets: float = 14_000_000.0,
    current_core: float = 7_000_000.0,
    prior_core: float = 6_000_000.0,
    current_share: float = 0.14,
    prior_share: float = 0.20,
) -> list[dict]:
    prior_quarter = f"{int(quarter[:4]) - 1}{quarter[4:]}"
    domestic_deposits = 10_000_000.0
    return [
        _row(
            quarter=prior_quarter,
            ticker=ticker,
            bank_id=bank_id,
            parent_group_id=parent_group_id,
            bank_assets=prior_assets,
            parent_assets=parent_assets,
            core_deposits=prior_core,
            uninsured_deposits=prior_share * domestic_deposits,
            domestic_deposits=domestic_deposits,
        ),
        _row(
            quarter=quarter,
            ticker=ticker,
            bank_id=bank_id,
            parent_group_id=parent_group_id,
            bank_assets=current_assets,
            parent_assets=parent_assets,
            core_deposits=current_core,
            uninsured_deposits=current_share * domestic_deposits,
            domestic_deposits=domestic_deposits,
        ),
    ]


def _weekdays(start: str, count: int) -> list[str]:
    current = date.fromisoformat(start)
    output: list[str] = []
    while len(output) < count:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _bars(start: str, count: int, *, initial: float = 100.0) -> list[dict]:
    rows: list[dict] = []
    close = initial
    for idx, day in enumerate(_weekdays(start, count)):
        open_price = close
        close = open_price * (1.002 if idx else 1.0)
        rows.append(
            {
                "date": day,
                "open": open_price,
                "high": max(open_price, close) + 0.5,
                "low": min(open_price, close) - 0.5,
                "close": close,
            }
        )
    return rows


def test_official_release_map_is_frozen_and_entry_is_strictly_after_release() -> None:
    assert sleeve.QBP_RELEASE_DATES == {
        "2024Q3": "2024-12-12",
        "2024Q4": "2025-02-25",
        "2025Q1": "2025-05-28",
        "2025Q2": "2025-08-26",
        "2025Q3": "2025-11-24",
        "2025Q4": "2026-02-24",
    }
    candidates, _ = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=_pair(parent_group_id="9001"),
        trading_dates=["2024-12-12", "2024-12-13", "2024-12-16"],
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["release_date"] == "2024-12-12"
    assert candidate["signal_date"] == "2024-12-12"
    assert candidate["entry_date"] == "2024-12-13"
    assert candidate["entry_date"] > candidate["release_date"]
    assert candidate["parent_group_id"] == "9001"
    assert candidate["parent_group_id_source"] == "regulatory_parent_id"


def test_dominant_insured_bank_must_represent_at_least_80pct_of_parent() -> None:
    passing, _ = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=_pair(current_assets=12_000_000, parent_assets=15_000_000),
        trading_dates=["2024-12-13"],
    )
    failing, audit = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=_pair(current_assets=12_000_000, parent_assets=15_000_001),
        trading_dates=["2024-12-13"],
    )
    assert passing[0]["dominant_bank_asset_share"] == pytest.approx(0.8)
    assert failing == []
    assert audit["reject_totals"]["dominant_bank_share_below_80pct"] == 1


def test_largest_insured_bank_is_used_for_parent_dominance() -> None:
    rows = _pair(bank_id="large", current_assets=12_000_000, parent_assets=14_000_000)
    rows.extend(
        _pair(
            bank_id="small",
            current_assets=2_000_000,
            prior_assets=1_900_000,
            parent_assets=14_000_000,
        )
    )
    candidates, _ = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=rows,
        trading_dates=["2024-12-13"],
    )
    assert len(candidates) == 1
    assert candidates[0]["bank_id"] == "large"


def test_same_ticker_in_two_parent_groups_fails_closed() -> None:
    rows = _pair(
        ticker="BANK",
        bank_id="100",
        parent_group_id="9001",
    )
    rows.extend(
        _pair(
            ticker="BANK",
            bank_id="200",
            parent_group_id="9002",
        )
    )
    candidates, audit = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=rows,
        trading_dates=["2024-12-13"],
    )
    assert candidates == []
    assert audit["reject_totals"]["ticker_multiple_parent_groups"] == 1
    assert audit["parent_group_id_fallback_record_count"] == 0
    assert audit["ambiguous_tickers"] == [
        {
            "quarter": "2024Q3",
            "ticker": "BANK",
            "parent_group_ids": ["9001", "9002"],
        }
    ]


def test_same_parent_group_with_two_tickers_fails_closed() -> None:
    rows = _pair(
        ticker="BANKA",
        bank_id="100",
        parent_group_id="9001",
    )
    rows.extend(
        _pair(
            ticker="BANKB",
            bank_id="200",
            parent_group_id="9001",
        )
    )
    candidates, audit = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=rows,
        trading_dates=["2024-12-13"],
    )
    assert candidates == []
    assert audit["reject_totals"]["parent_group_multiple_tickers"] == 1
    assert audit["ambiguous_parent_groups"] == [
        {
            "quarter": "2024Q3",
            "parent_group_id": "9001",
            "tickers": ["BANKA", "BANKB"],
        }
    ]


def test_asset_growth_merger_gate_rejects_above_25pct_absolute_yoy() -> None:
    passing, _ = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=_pair(current_assets=12_500_000, prior_assets=10_000_000),
        trading_dates=["2024-12-13"],
    )
    failing, audit = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=_pair(current_assets=12_600_000, prior_assets=10_000_000),
        trading_dates=["2024-12-13"],
    )
    assert len(passing) == 1
    assert failing == []
    assert audit["reject_totals"]["asset_growth_merger_gate"] == 1


def test_core_growth_and_uninsured_share_direction_are_hard_gates() -> None:
    no_core_growth, core_audit = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=_pair(current_core=6_000_000, prior_core=6_000_000),
        trading_dates=["2024-12-13"],
    )
    no_share_repair, share_audit = (
        sleeve.build_fdic_call_report_deposit_repair_candidates(
            records=_pair(current_share=0.20, prior_share=0.20),
            trading_dates=["2024-12-13"],
        )
    )
    assert no_core_growth == []
    assert core_audit["reject_totals"]["core_deposits_yoy_not_positive"] == 1
    assert no_share_repair == []
    assert share_audit["reject_totals"]["uninsured_share_yoy_not_declining"] == 1


def test_uninsured_share_uses_depdom_and_never_falls_back_to_dep() -> None:
    rows = _pair(current_share=0.14, prior_share=0.20)
    # If the implementation accidentally divides by DEP, the shares become
    # 7% and 40% rather than the intended DEPDOM-based 14% and 20%.
    rows[0]["DEP"] = 5_000_000.0
    rows[1]["DEP"] = 20_000_000.0
    candidates, audit = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=rows,
        trading_dates=["2024-12-13"],
    )
    assert len(candidates) == 1
    assert candidates[0]["uninsured_deposit_share"] == pytest.approx(0.14)
    assert candidates[0]["prior_uninsured_deposit_share"] == pytest.approx(0.20)
    assert candidates[0]["uninsured_share_yoy_delta"] == pytest.approx(-0.06)
    assert candidates[0]["uninsured_deposit_share_denominator"] == "DEPDOM"
    assert candidates[0]["uninsured_deposit_share_formula"] == "DEPUNINS/DEPDOM"
    assert audit["uninsured_deposit_share_denominator"] == "DEPDOM"

    missing_depdom = [dict(row) for row in rows]
    for row in missing_depdom:
        row.pop("DEPDOM")
    rejected, rejected_audit = (
        sleeve.build_fdic_call_report_deposit_repair_candidates(
            records=missing_depdom,
            trading_dates=["2024-12-13"],
        )
    )
    assert rejected == []
    assert rejected_audit["normalised_record_count"] == 0
    assert rejected_audit["reject_totals"]["missing_required_fdic_field"] == 2


def test_each_quarter_ranks_delta_ascending_and_keeps_fixed_top5() -> None:
    rows: list[dict] = []
    deltas = {
        "B0": -0.01,
        "B1": -0.06,
        "B2": -0.03,
        "B3": -0.05,
        "B4": -0.02,
        "B5": -0.04,
    }
    for idx, (ticker, delta) in enumerate(deltas.items()):
        rows.extend(
            _pair(
                ticker=ticker,
                bank_id=str(100 + idx),
                current_share=0.20 + delta,
                prior_share=0.20,
            )
        )
    candidates, audit = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=rows,
        trading_dates=["2024-12-13"],
    )
    assert [row["ticker"] for row in candidates] == ["B1", "B3", "B5", "B2", "B4"]
    assert [row["quarter_rank"] for row in candidates] == [1, 2, 3, 4, 5]
    assert audit["eligible_by_quarter"] == {"2024Q3": 6}
    assert audit["selected_by_quarter"] == {"2024Q3": 5}
    assert audit["reject_totals"]["quarterly_top5_limit"] == 1


def test_generated_denominator_counts_only_parent_quarters_in_replay_window() -> None:
    rows = _pair(
        quarter="2024Q3",
        ticker="Q3BANK",
        bank_id="300",
        parent_group_id="9300",
    )
    rows.extend(
        _pair(
            quarter="2024Q4",
            ticker="Q4BANK",
            bank_id="400",
            parent_group_id="9400",
        )
    )
    candidates, audit = sleeve.build_fdic_call_report_deposit_repair_candidates(
        records=rows,
        trading_dates=[
            "2024-12-12",
            "2024-12-13",
            "2025-02-25",
            "2025-02-26",
        ],
        start="2024-12-01",
        end="2024-12-31",
    )
    assert [row["ticker"] for row in candidates] == ["Q3BANK"]
    assert audit["quarter_rows_considered"] == 1
    assert audit["selected_count"] == 1
    assert audit["out_of_window_parent_quarter_groups"] == 1


def test_replay_uses_next_open_and_twentieth_session_close() -> None:
    spy = _bars("2024-12-02", 40)
    bank = _bars("2024-12-02", 40, initial=80.0)
    replay = sleeve.replay_fdic_call_report_deposit_repair_paper_trades(
        records=_pair(),
        ohlcv_by_ticker={"SPY": spy, "BANK": bank},
        start="2024-12-01",
        end="2025-01-31",
    )
    assert len(replay["trades"]) == 1
    trade = replay["trades"][0]
    entry_idx = next(idx for idx, row in enumerate(bank) if row["date"] == "2024-12-13")
    assert trade["entry_date"] == "2024-12-13"
    assert trade["exit_date"] == bank[entry_idx + 19]["date"]
    assert trade["hold_sessions_realized"] == 20
    assert trade["target_price"] > trade["entry_price"]
    assert trade["trade_enabled"] is False
    assert replay["orders"] == []


def test_snapshot_is_default_off_and_can_never_emit_orders() -> None:
    snapshot = sleeve.build_fdic_call_report_deposit_repair_paper_sleeve_snapshot(
        as_of_date="2024-12-12",
        records=_pair(),
        trading_dates=["2024-12-12", "2024-12-13"],
    )
    assert snapshot["candidate_count"] == 1
    assert snapshot["enabled"] is False
    assert snapshot["paper_enabled"] is True
    assert snapshot["trade_enabled"] is False
    assert snapshot["orders"] == []
    assert snapshot["alters_orders"] is False
    assert snapshot["production_impact"] == {
        "trade_enabled": False,
        "alters_orders": False,
        "alters_live_orders": False,
        "alters_core_signal_generation": False,
        "alters_core_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
    }
    assert all(row["trade_enabled"] is False for row in snapshot["candidates"])
