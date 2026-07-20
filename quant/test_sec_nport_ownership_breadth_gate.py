from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from entry_universe_ledger import membership_hash  # noqa: E402
from sec_nport_ownership_breadth_gate import (  # noqa: E402
    MIN_MATCHED_SERIES,
    NPortOwnershipBreadthEntryResolver,
    RULE_VERSION,
    build_daily_ownership_breadth_snapshot,
    compute_ownership_breadth_decision,
)
from sec_nport_share_accumulation import load_nport_rows  # noqa: E402


def _report(series: str, report_date: str, filing_date: str, accession: str) -> dict:
    return {
        "accession": accession,
        "series_id": series,
        "report_date": report_date,
        "filing_date": filing_date,
    }


def _holding(
    series: str,
    report_date: str,
    filing_date: str,
    accession: str,
    *,
    ticker: str = "ABC",
) -> dict:
    return {
        **_report(series, report_date, filing_date, accession),
        "ticker": ticker,
        "balance": 10.0,
        "currency_value": 1000.0,
    }


def _breadth_dataset(
    *,
    bought: int,
    sold: int,
    continuous: int,
    current_filing_date: str = "2024-08-15",
):
    count = bought + sold + continuous
    reports: list[dict] = []
    holdings: list[dict] = []
    for index in range(count):
        series = f"S{index:04d}"
        previous_accession = f"P{index:04d}"
        current_accession = f"C{index:04d}"
        reports.extend(
            [
                _report(series, "2024-03-31", "2024-05-15", previous_accession),
                _report(
                    series,
                    "2024-06-30",
                    current_filing_date,
                    current_accession,
                ),
            ]
        )
        if index < sold or index >= sold + bought:
            holdings.append(
                _holding(
                    series,
                    "2024-03-31",
                    "2024-05-15",
                    previous_accession,
                )
            )
        if sold <= index < sold + bought or index >= sold + bought:
            holdings.append(
                _holding(
                    series,
                    "2024-06-30",
                    current_filing_date,
                    current_accession,
                )
            )
    return load_nport_rows(holdings, reports)


def _sessions() -> list[str]:
    return [
        "2024-08-14",
        "2024-08-15",
        "2024-08-16",
        "2024-08-19",
    ]


def _source_identity() -> dict:
    return {
        "schema": "test_nport_source_identity_v1",
        "bundle_sha256": "a" * 64,
        "files": [{"path": "nport.json.gz", "sha256": "b" * 64}],
    }


def test_strict_pit_breadth_counts_and_negative_decision() -> None:
    dataset = _breadth_dataset(bought=3, sold=12, continuous=5)

    # A filing dated on the action session is not usable: the source helper
    # enforces filing_date < action_date and missing breadth fails open.
    same_day = compute_ownership_breadth_decision(dataset, "2024-08-15", "abc")
    assert same_day["status"] == "missing"
    assert same_day["breadth_score"] is None
    assert same_day["fresh_entry_eligible"] is True
    assert same_day["filing_date_rule"] == (
        "filing_date_strictly_before_action_date"
    )

    following_day = compute_ownership_breadth_decision(
        dataset, "2024-08-16", "ABC"
    )
    assert following_day["matched_series_count"] == MIN_MATCHED_SERIES
    assert following_day["bought_from_zero_series_count"] == 3
    assert following_day["sold_to_zero_series_count"] == 12
    assert following_day["continuous_holder_series_count"] == 5
    assert following_day["breadth_score"] == -9 / MIN_MATCHED_SERIES
    assert following_day["status"] == "negative"
    assert following_day["fresh_entry_eligible"] is False
    assert following_day["alters_addons"] is False
    assert following_day["alters_existing_positions"] is False
    assert compute_ownership_breadth_decision(
        dataset,
        "2024-08-16",
        "ABC",
        raw_prices=lambda *_: (_ for _ in ()).throw(
            AssertionError("non-causal price lookup was executed")
        ),
    ) == following_day


def test_zero_and_missing_breadth_fail_open() -> None:
    zero = compute_ownership_breadth_decision(
        _breadth_dataset(bought=5, sold=5, continuous=10),
        "2024-08-16",
        "ABC",
    )
    assert zero["matched_series_count"] == MIN_MATCHED_SERIES
    assert zero["breadth_score"] == 0.0
    assert zero["status"] == "neutral"
    assert zero["fresh_entry_eligible"] is True
    assert zero["reason"] == "fail_open_zero_ownership_breadth"

    insufficient = compute_ownership_breadth_decision(
        _breadth_dataset(bought=0, sold=10, continuous=9),
        "2024-08-16",
        "ABC",
    )
    assert insufficient["matched_series_count"] == MIN_MATCHED_SERIES - 1
    assert insufficient["breadth_score"] is None
    assert insufficient["fresh_entry_eligible"] is True
    assert insufficient["reason"] == "fail_open_insufficient_matched_series"


def test_resolver_uses_next_session_and_backtester_provenance_contract() -> None:
    dataset = _breadth_dataset(bought=3, sold=12, continuous=5)
    resolver = NPortOwnershipBreadthEntryResolver(
        ["ABC", "XYZ"], dataset, _sessions(), _source_identity()
    )

    # Aug 14 signal -> Aug 15 action: same-day filing is unavailable, so ABC
    # fails open.  Aug 15 signal -> Aug 16 action: breadth is negative.
    assert resolver("2024-08-14") == {"ABC", "XYZ"}
    assert resolver("2024-08-15") == {"XYZ"}
    resolved = resolver.resolve("2024-08-15")
    assert resolved["membership_hash"] == membership_hash(["XYZ"])
    assert resolved["provenance"]["signal_date"] == "2024-08-15"
    assert resolved["provenance"]["action_date"] == "2024-08-16"
    assert resolved["provenance"]["excluded_tickers"] == ["ABC"]
    assert resolved["provenance"]["missing_tickers"] == ["XYZ"]
    assert resolved["provenance"]["ticker_decisions"]["ABC"][
        "breadth_score"
    ] == -9 / MIN_MATCHED_SERIES
    assert resolver.metadata["rule_version"] == RULE_VERSION
    assert resolver.metadata["policy"]["scope"] == "fresh_core_entries_only"

    from quant.backtester import BacktestEngine

    engine = object.__new__(BacktestEngine)
    engine.universe = ["ABC", "XYZ"]
    engine.entry_universe_resolver = resolver
    eligible, provenance = BacktestEngine._core_entry_universe_as_of(
        engine, "2024-08-15"
    )
    assert eligible == {"XYZ"}
    assert provenance["source"] == resolved["source"]
    assert provenance["snapshot_sha256"] == resolved["snapshot_sha256"]


def test_resolver_copies_calendar_and_source_identity_with_deterministic_hashes() -> None:
    dataset = _breadth_dataset(bought=3, sold=12, continuous=5)
    sessions = _sessions()
    identity = _source_identity()
    original_identity = deepcopy(identity)
    resolver = NPortOwnershipBreadthEntryResolver(
        ["XYZ", "ABC"], dataset, sessions, identity
    )
    metadata = resolver.metadata
    first = resolver.resolve("2024-08-15")

    sessions.clear()
    sessions.append("2099-01-01")
    identity["files"][0]["sha256"] = "c" * 64
    identity["new_field"] = "caller mutation"

    assert resolver.metadata == metadata
    assert resolver.resolve("2024-08-15") == first
    assert first["provenance"]["entry_session"] == "2024-08-16"
    assert len(first["snapshot_sha256"]) == 64
    assert len(first["record_hash"]) == 64
    clone = NPortOwnershipBreadthEntryResolver(
        ["ABC", "XYZ"], dataset, _sessions(), original_identity
    )
    assert clone.metadata == metadata
    assert clone.resolve("2024-08-15") == first


def test_daily_snapshot_matches_resolver_and_cannot_trade() -> None:
    dataset = _breadth_dataset(bought=3, sold=12, continuous=5)
    identity = _source_identity()
    resolver = NPortOwnershipBreadthEntryResolver(
        ["ABC", "XYZ"], dataset, _sessions(), identity
    )
    resolved = resolver.resolve("2024-08-15")
    daily = build_daily_ownership_breadth_snapshot(
        dataset,
        "2024-08-15",
        _sessions(),
        ["XYZ", "ABC"],
        base_tickers=["ABC", "XYZ"],
        source_identity=identity,
    )

    assert daily["next_trading_session"] == "2024-08-16"
    assert daily["eligible_tickers"] == resolved["tickers"] == ["XYZ"]
    assert daily["excluded_tickers_for_next_session"] == ["ABC"]
    assert daily["excluded_tickers"] == ["ABC"]
    assert daily["excluded_candidate_tickers"] == ["ABC"]
    assert daily["fail_open_candidate_tickers"] == ["XYZ"]
    assert daily["resolver_snapshot_hash"] == resolved["snapshot_sha256"]
    assert daily["resolver_record_hash"] == resolved["record_hash"]
    assert daily["membership_hash"] == resolved["membership_hash"]
    assert daily["trade_enabled"] is False
    assert daily["can_place_orders"] is False
    assert daily["orders"] == []
    assert daily["order_intents"] == []
    assert daily["alters_existing_positions"] is False
    assert daily["alters_addons"] is False
    assert daily["alters_ranking"] is False
    assert daily["alters_sizing"] is False
    assert daily["alters_exits"] is False
    assert daily["alters_costs"] is False
    assert all(row["trade_enabled"] is False for row in daily["candidates"])
    assert all(row["can_place_orders"] is False for row in daily["candidates"])
