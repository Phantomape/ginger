from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from quant.constants import ROUND_TRIP_COST_PCT
from quant.deps_dev_maven_release_acceleration_paper_sleeve import (
    COORDINATE_TO_ISSUER,
    HOLD_SESSIONS,
    ISSUER_PACKAGE_COORDINATES,
    PAPER_NOTIONAL_USD,
    DepsDevMavenReleaseContractError,
    build_deps_dev_maven_release_acceleration_historical_trades,
    build_deps_dev_maven_release_acceleration_snapshot,
    normalise_deps_dev_maven_release_rows,
    select_deps_dev_maven_release_acceleration_weekly_decisions,
)
from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET


def _release(
    coordinate: str,
    version: str,
    published_at: str,
) -> dict[str, object]:
    return {
        "package": coordinate,
        "version": version,
        "publishedAt": published_at,
    }


def _week_releases(
    *,
    ticker: str,
    monday: str,
    count: int,
    prefix: str,
) -> list[dict[str, object]]:
    coordinate = ISSUER_PACKAGE_COORDINATES[ticker][0]
    start = date.fromisoformat(monday)
    return [
        _release(
            coordinate,
            f"{prefix}.{index}",
            datetime.combine(
                start + timedelta(days=index % 6),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            .replace(hour=12)
            .isoformat()
            .replace("+00:00", "Z"),
        )
        for index in range(count)
    ]


def _business_bars(start: str, count: int, *, slope: float = 0.4):
    day = date.fromisoformat(start)
    rows = []
    index = 0
    while len(rows) < count:
        if day.weekday() < 5:
            close = 100.0 + index * slope
            rows.append(
                {
                    "date": day.isoformat(),
                    "open": close - 0.2,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                }
            )
            index += 1
        day += timedelta(days=1)
    return rows


def test_frozen_exact_effective_dated_map_and_snapshot_filter():
    assert len(COORDINATE_TO_ISSUER) == 29
    assert COORDINATE_TO_ISSUER["software.amazon.awssdk:bom"] == {
        "ticker": "AMZN",
        "effective_from": "2024-01-01",
    }
    assert COORDINATE_TO_ISSUER["co.elastic.clients:elasticsearch-java"] == {
        "ticker": "ESTC",
        "effective_from": "2024-01-01",
    }
    assert COORDINATE_TO_ISSUER["com.splunk:opentelemetry-javaagent"] == {
        "ticker": "CSCO",
        "effective_from": "2024-03-18",
    }

    row = _release(
        "software.amazon.awssdk:bom",
        "2.31.0",
        "2025-02-03T12:00:00Z",
    )
    rows = normalise_deps_dev_maven_release_rows(
        [
            row,
            dict(row),
            _release(
                "software.amazon.awssdk:bom",
                "2.31.1-SNAPSHOT",
                "2025-02-04T12:00:00Z",
            ),
            _release(
                "software.amazon.awssdk:not-frozen",
                "1.0.0",
                "2025-02-04T12:00:00Z",
            ),
            _release(
                "software.amazon.awssdk:bom",
                "0.1.0",
                "2023-12-31T12:00:00Z",
            ),
            _release(
                "com.splunk:opentelemetry-javaagent",
                "2.1.0",
                "2024-03-17T12:00:00Z",
            ),
        ]
    )
    assert len(rows) == 1
    assert rows[0]["package_coordinate"] == "software.amazon.awssdk:bom"
    assert rows[0]["ticker"] == "AMZN"
    assert rows[0]["version"] == "2.31.0"


def test_duplicate_package_version_publication_conflict_fails_closed():
    with pytest.raises(DepsDevMavenReleaseContractError, match="conflicting"):
        normalise_deps_dev_maven_release_rows(
            [
                _release(
                    "software.amazon.awssdk:bom",
                    "2.31.0",
                    "2025-02-03T12:00:00Z",
                ),
                _release(
                    "software.amazon.awssdk:bom",
                    "2.31.0",
                    "2025-02-04T12:00:00Z",
                ),
            ]
        )


def test_complete_week_prior_eight_median_and_strict_acceleration_are_pit():
    releases: list[dict[str, object]] = []
    first_prior = date.fromisoformat("2024-12-09")
    amzn_counts = [1, 1, 1, 1, 2, 2, 2, 2]
    for index, count in enumerate(amzn_counts):
        monday = (first_prior + timedelta(days=7 * index)).isoformat()
        releases.extend(
            _week_releases(
                ticker="AMZN",
                monday=monday,
                count=count,
                prefix=f"amzn-prior-{index}",
            )
        )
        releases.extend(
            _week_releases(
                ticker="GOOGL",
                monday=monday,
                count=3,
                prefix=f"googl-prior-{index}",
            )
        )
    releases.extend(
        _week_releases(ticker="AMZN", monday="2025-02-03", count=3, prefix="amzn-now")
    )
    releases.extend(
        _week_releases(ticker="GOOGL", monday="2025-02-03", count=3, prefix="googl-now")
    )
    releases.extend(
        _week_releases(ticker="MSFT", monday="2025-02-03", count=1, prefix="msft-now")
    )

    assert (
        select_deps_dev_maven_release_acceleration_weekly_decisions(
            releases,
            as_of="2025-02-09",
            archive_start="2024-12-09",
        )
        == []
    )
    decisions = select_deps_dev_maven_release_acceleration_weekly_decisions(
        releases,
        as_of="2025-02-10",
        archive_start="2024-12-09",
    )
    assert [row["ticker"] for row in decisions] == ["AMZN"]
    assert decisions[0]["week_end"] == "2025-02-09"
    assert decisions[0]["prior_eight_week_counts"] == amzn_counts
    assert decisions[0]["prior_eight_week_median"] == 1.5
    assert decisions[0]["current_release_count"] == 3
    assert decisions[0]["release_acceleration"] == 1.5
    # GOOGL equals its prior median; MSFT fails current count >= 2.


def test_top_three_historical_snapshot_parity_and_h10_timing():
    releases: list[dict[str, object]] = []
    for ticker, count in (("AMZN", 5), ("MSFT", 4), ("GOOGL", 3), ("ORCL", 2)):
        releases.extend(
            _week_releases(
                ticker=ticker,
                monday="2025-02-03",
                count=count,
                prefix=f"{ticker.lower()}-now",
            )
        )
    bars = _business_bars("2025-01-01", 70)
    market = {ticker: bars for ticker in ("SPY", "AMZN", "MSFT", "GOOGL", "ORCL")}
    replay = build_deps_dev_maven_release_acceleration_historical_trades(
        release_rows=releases,
        ohlcv_by_ticker=market,
        start="2025-02-01",
        end="2025-03-10",
        archive_start="2024-12-09",
    )
    assert [row["ticker"] for row in replay["window_decisions"]] == [
        "AMZN",
        "MSFT",
        "GOOGL",
    ]
    assert replay["trade_enabled"] is False
    assert len(replay["trades"]) == 3
    for trade in replay["trades"]:
        assert trade["entry_date"] == "2025-02-10"
        assert trade["exit_date"] == "2025-02-21"
        assert trade["hold_sessions_realized"] == HOLD_SESSIONS
        assert trade["target_price"] > trade["entry_price"]
        assert trade["paper_notional_usd"] == PAPER_NOTIONAL_USD
        assert trade["round_trip_cost_pct"] == ROUND_TRIP_COST_PCT
        assert trade["entry_slippage_bps"] == SLIPPAGE_BPS_ENTRY
        assert trade["exit_slippage_bps"] == SLIPPAGE_BPS_TARGET
        assert trade["trade_enabled"] is False
        assert trade["alters_orders"] is False

    snapshot = build_deps_dev_maven_release_acceleration_snapshot(
        release_rows=releases,
        ohlcv_by_ticker=market,
        as_of="2025-03-10",
        start="2025-02-01",
        archive_start="2024-12-09",
        persist=False,
    )
    assert snapshot["trade_enabled"] is False
    assert snapshot["alters_orders"] is False
    assert snapshot["execution_envelope"]["max_concurrent_positions"] == 6
    assert snapshot["execution_envelope"]["one_active_position_per_ticker"] is True
    assert [
        row["decision_id"] for row in snapshot["replay"]["window_decisions"]
    ] == [row["decision_id"] for row in replay["window_decisions"]]
    assert [
        (row["decision_id"], row["entry_date"], row["exit_date"])
        for row in snapshot["replay"]["trades"]
    ] == [
        (row["decision_id"], row["entry_date"], row["exit_date"])
        for row in replay["trades"]
    ]


def test_one_active_position_per_ticker_rejects_overlapping_week():
    releases: list[dict[str, object]] = []
    releases.extend(
        _week_releases(ticker="AMZN", monday="2025-02-03", count=2, prefix="first")
    )
    releases.extend(
        _week_releases(ticker="AMZN", monday="2025-02-10", count=3, prefix="second")
    )
    bars = _business_bars("2025-01-01", 70)
    replay = build_deps_dev_maven_release_acceleration_historical_trades(
        release_rows=releases,
        ohlcv_by_ticker={"SPY": bars, "AMZN": bars},
        start="2025-02-01",
        end="2025-03-10",
        archive_start="2024-12-09",
    )
    assert len(replay["window_decisions"]) == 2
    assert len(replay["trade_candidates"]) == 1
    assert replay["reject_totals"] == {"same_ticker_active": 1}
    assert replay["trade_candidates"][0]["entry_date"]
    assert replay["trade_candidates"][0]["target_price"]


def test_optional_snapshot_persistence_uses_injected_paths(tmp_path):
    releases = _week_releases(
        ticker="AMZN", monday="2025-02-03", count=2, prefix="persist"
    )
    bars = _business_bars("2025-01-01", 45)
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshots.jsonl"
    snapshot = build_deps_dev_maven_release_acceleration_snapshot(
        release_rows=releases,
        ohlcv_by_ticker={"SPY": bars, "AMZN": bars},
        as_of="2025-02-14",
        start="2025-02-01",
        archive_start="2024-12-09",
        persist=True,
        state_path=state_path,
        snapshot_log_path=snapshot_path,
    )
    assert state_path.exists()
    assert snapshot_path.exists()
    assert snapshot["trade_enabled"] is False
    assert snapshot["replay"]["trade_candidates"][0]["entry_date"]
    assert snapshot["replay"]["trade_candidates"][0]["target_price"]
