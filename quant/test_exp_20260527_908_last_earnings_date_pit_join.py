"""Unit tests for exp-20260527-908 PIT ``last_earnings_date`` join.

These tests use synthetic earnings snapshots written into a tmp directory so
they do not depend on the live repo data. They verify:

* PIT safety: future snapshots are not consulted.
* PIT safety: a ``next_earnings_date`` that has not yet passed is not
  reported as a past earnings.
* Most-recent semantics: when multiple past earnings exist, the most
  recent one wins.
* Missing ticker / empty ticker fallbacks return well-formed lookups.
* Enrichment writes ``last_earnings_date`` and updates ``pead_status``
  without mutating the input rows.
* Gate 4 acceptance rule requires both >=80% primary-positive coverage
  *and* at least one inside/outside-T+2..T+15 bucket.

No JavaScript was used.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant.experiments.exp_20260527_908_last_earnings_date_pit_join_into_expectation_revision_watchlist_row import (  # noqa: E501
    build_pit_earnings_index,
    build_pit_earnings_index_from_sec,
    coverage_report,
    enrich_watchlist_rows,
    evaluate_gates,
    last_earnings_date_pit,
    last_earnings_date_pit_sec,
    pead_readiness_reprobe,
    recompute_pead_status,
)


def _write_snapshot(
    dir_: Path, snap_date_yyyymmdd: str, earnings: dict[str, dict]
) -> None:
    payload = {
        "schema_version": 1,
        "date": snap_date_yyyymmdd,
        "timestamp": "2026-01-01T00:00:00",
        "coverage": {"tickers_total": len(earnings)},
        "earnings": earnings,
    }
    (dir_ / f"earnings_snapshot_{snap_date_yyyymmdd}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


@pytest.fixture()
def snapshot_dir(tmp_path: Path) -> Path:
    d = tmp_path / "earnings_snapshots"
    d.mkdir()
    # Day 1: AAPL's next earnings is in the future.
    _write_snapshot(
        d,
        "20260401",
        {"AAPL": {"next_earnings_date": "2026-05-01"}, "MSFT": {"next_earnings_date": "2026-04-25"}},
    )
    # Day 2: MSFT has reported (2026-04-25 <= 2026-04-26).
    _write_snapshot(
        d,
        "20260426",
        {"AAPL": {"next_earnings_date": "2026-05-01"}, "MSFT": {"next_earnings_date": "2026-07-20"}},
    )
    # Day 3: AAPL has now reported.
    _write_snapshot(
        d,
        "20260502",
        {"AAPL": {"next_earnings_date": "2026-07-30"}, "MSFT": {"next_earnings_date": "2026-07-20"}},
    )
    return d


def test_lookup_returns_no_past_when_query_is_before_any_earnings(snapshot_dir):
    index = build_pit_earnings_index(snapshot_dir)
    result = last_earnings_date_pit("AAPL", "2026-04-15", index)
    assert result["last_earnings_date"] is None
    assert result["status"] == "no_past_earnings_within_window"


def test_lookup_returns_most_recent_past_earnings(snapshot_dir):
    index = build_pit_earnings_index(snapshot_dir)
    # On 2026-05-05, AAPL has reported on 2026-05-01 but MSFT also on 2026-04-25.
    result = last_earnings_date_pit("AAPL", "2026-05-05", index)
    assert result["last_earnings_date"] == "2026-05-01"
    assert result["status"] == "ok"


def test_lookup_is_pit_safe_no_future_snapshot_leak(snapshot_dir, tmp_path: Path):
    """If we query as of 2026-04-25, snapshots dated 2026-04-26 / 2026-05-02
    must not be consulted — otherwise we would learn MSFT reported on
    2026-04-25 by reading a snapshot that did not exist yet."""
    index = build_pit_earnings_index(snapshot_dir)
    # On 2026-04-25, only the 2026-04-01 snapshot is visible — MSFT's next
    # earnings was 2026-04-25, which equals as_of so it counts.
    msft = last_earnings_date_pit("MSFT", "2026-04-25", index)
    assert msft["last_earnings_date"] == "2026-04-25"
    # But on 2026-04-24, the 2026-04-25 earnings has *not* happened yet.
    msft_pre = last_earnings_date_pit("MSFT", "2026-04-24", index)
    assert msft_pre["last_earnings_date"] is None
    assert msft_pre["status"] == "no_past_earnings_within_window"


def test_lookup_unknown_ticker_returns_ticker_not_in_snapshots(snapshot_dir):
    index = build_pit_earnings_index(snapshot_dir)
    result = last_earnings_date_pit("FAKEXYZ", "2026-05-10", index)
    assert result["last_earnings_date"] is None
    assert result["status"] == "ticker_not_in_snapshots"


def test_lookup_empty_ticker_returns_empty_ticker_status(snapshot_dir):
    index = build_pit_earnings_index(snapshot_dir)
    result = last_earnings_date_pit("", "2026-05-10", index)
    assert result["last_earnings_date"] is None
    assert result["status"] == "empty_ticker"


def test_lookup_case_insensitive(snapshot_dir):
    index = build_pit_earnings_index(snapshot_dir)
    result = last_earnings_date_pit("aapl", "2026-05-05", index)
    assert result["last_earnings_date"] == "2026-05-01"
    assert result["status"] == "ok"


def test_recompute_pead_status_inside_window():
    out = recompute_pead_status("2026-05-05", "2026-05-01")
    assert out["pead_status"] == "inside_t2_t15_after_earnings"
    assert out["pead_window"] is True
    assert out["days_since_last_earnings"] == 4


def test_recompute_pead_status_outside_window():
    out = recompute_pead_status("2026-06-10", "2026-05-01")
    assert out["pead_status"] == "outside_t2_t15_after_earnings"
    assert out["pead_window"] is False
    assert out["days_since_last_earnings"] == 40


def test_recompute_pead_status_missing_field():
    assert (
        recompute_pead_status("2026-05-05", None)["pead_status"]
        == "missing_last_earnings_date"
    )
    assert (
        recompute_pead_status(None, "2026-05-01")["pead_status"]
        == "missing_effective_trade_date"
    )


def test_enrich_does_not_mutate_input(snapshot_dir):
    index = build_pit_earnings_index(snapshot_dir)
    rows = [
        {
            "ticker": "AAPL",
            "as_of_date": "2026-05-05",
            "watchlist_effective_trade_date": "2026-05-05",
            "pead_status": "missing_last_earnings_date",
            "primary_expectation_positive": True,
        }
    ]
    snapshot = json.dumps(rows, sort_keys=True)
    enriched = enrich_watchlist_rows(rows, {}, snapshot_index=index)
    assert enriched[0]["last_earnings_date"] == "2026-05-01"
    assert enriched[0]["pead_status"] == "inside_t2_t15_after_earnings"
    assert enriched[0]["pead_status_before_repair"] == "missing_last_earnings_date"
    # original list is untouched
    assert json.dumps(rows, sort_keys=True) == snapshot


def test_coverage_and_gate4_pass_when_field_resolves(snapshot_dir):
    index = build_pit_earnings_index(snapshot_dir)
    rows = [
        # Two primary positive rows; both should resolve.
        {
            "ticker": "AAPL",
            "as_of_date": "2026-05-05",
            "watchlist_effective_trade_date": "2026-05-05",
            "pead_status": "missing_last_earnings_date",
            "primary_expectation_positive": True,
        },
        {
            "ticker": "MSFT",
            "as_of_date": "2026-04-26",
            "watchlist_effective_trade_date": "2026-04-26",
            "pead_status": "missing_last_earnings_date",
            "primary_expectation_positive": True,
        },
    ]
    enriched = enrich_watchlist_rows(rows, {}, snapshot_index=index)
    cov = coverage_report(enriched, rows)
    gates = evaluate_gates(cov)
    assert gates["gate4"]["passed"] is True
    assert gates["all_passed"] is True
    assert cov["last_earnings_date_coverage"]["primary_positive_rows"]["ratio"] == 1.0


def test_gate4_fails_when_coverage_below_80_pct(snapshot_dir):
    index = build_pit_earnings_index(snapshot_dir)
    # 1 of 2 primary positives resolves (FAKEXYZ does not).
    rows = [
        {
            "ticker": "AAPL",
            "as_of_date": "2026-05-05",
            "watchlist_effective_trade_date": "2026-05-05",
            "primary_expectation_positive": True,
            "pead_status": "missing_last_earnings_date",
        },
        {
            "ticker": "FAKEXYZ",
            "as_of_date": "2026-05-05",
            "watchlist_effective_trade_date": "2026-05-05",
            "primary_expectation_positive": True,
            "pead_status": "missing_last_earnings_date",
        },
    ]
    enriched = enrich_watchlist_rows(rows, {}, snapshot_index=index)
    cov = coverage_report(enriched, rows)
    gates = evaluate_gates(cov)
    assert gates["gate4"]["passed"] is False
    assert cov["last_earnings_date_coverage"]["primary_positive_rows"]["ratio"] == 0.5


def _write_sec_features(dir_: Path, snap_date_yyyymmdd: str, rows: list[dict]) -> None:
    p = dir_ / f"sec_filing_features_{snap_date_yyyymmdd}.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


@pytest.fixture()
def sec_features_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sec_features"
    d.mkdir()
    # AAPL 10-Q filed 2026-04-30
    _write_sec_features(
        d,
        "20260430",
        [
            {
                "ticker": "AAPL",
                "form_type": "10-Q",
                "filing_date": "2026-04-30",
                "event_date": "2026-04-30",
            }
        ],
    )
    # NVDA 8-K with item 2.02 filed 2026-05-21
    _write_sec_features(
        d,
        "20260521",
        [
            {
                "ticker": "NVDA",
                "form_type": "8-K",
                "eight_k_item_type": "2.02,9.01",
                "filing_date": "2026-05-21",
                "event_date": "2026-05-21",
            },
            # Same day, an unrelated 8-K without item 2.02 — must NOT count.
            {
                "ticker": "AAPL",
                "form_type": "8-K",
                "eight_k_item_type": "1.01,9.01",
                "filing_date": "2026-05-21",
                "event_date": "2026-05-21",
            },
        ],
    )
    # AAPL 10-K filed 2026-01-25 (earlier earnings)
    _write_sec_features(
        d,
        "20260125",
        [
            {
                "ticker": "AAPL",
                "form_type": "10-K",
                "filing_date": "2026-01-25",
                "event_date": "2026-01-25",
            }
        ],
    )
    return d


def test_sec_index_includes_10q_10k_and_8k_item_202(sec_features_dir):
    index = build_pit_earnings_index_from_sec(sec_features_dir)
    assert sorted(index.keys()) == ["AAPL", "NVDA"]
    aapl_pairs = index["AAPL"]
    # The 8-K without 2.02 must NOT be in AAPL's earnings timeline.
    assert ("2026-05-21", "2026-05-21") not in aapl_pairs
    # The 10-K and 10-Q must be present.
    assert ("2026-01-25", "2026-01-25") in aapl_pairs
    assert ("2026-04-30", "2026-04-30") in aapl_pairs


def test_sec_lookup_returns_most_recent_past_filing(sec_features_dir):
    index = build_pit_earnings_index_from_sec(sec_features_dir)
    out = last_earnings_date_pit_sec("AAPL", "2026-05-10", index)
    assert out["last_earnings_date"] == "2026-04-30"
    assert out["last_earnings_filing_date"] == "2026-04-30"
    assert out["status"] == "ok"


def test_sec_lookup_excludes_future_filings(sec_features_dir):
    index = build_pit_earnings_index_from_sec(sec_features_dir)
    # On 2026-04-29, AAPL's 2026-04-30 filing has not happened yet.
    out = last_earnings_date_pit_sec("AAPL", "2026-04-29", index)
    assert out["last_earnings_date"] == "2026-01-25"


def test_sec_lookup_unknown_ticker(sec_features_dir):
    index = build_pit_earnings_index_from_sec(sec_features_dir)
    out = last_earnings_date_pit_sec("FAKEXYZ", "2026-05-10", index)
    assert out["last_earnings_date"] is None
    assert out["status"] == "ticker_not_in_sec_filings"


def test_enrich_prefers_sec_then_falls_back_to_snapshot(
    sec_features_dir, snapshot_dir
):
    sec_index = build_pit_earnings_index_from_sec(sec_features_dir)
    snap_index = build_pit_earnings_index(snapshot_dir)
    rows = [
        # AAPL covered by SEC source.
        {
            "ticker": "AAPL",
            "as_of_date": "2026-05-10",
            "watchlist_effective_trade_date": "2026-05-10",
            "primary_expectation_positive": True,
            "pead_status": "missing_last_earnings_date",
        },
        # MSFT not in SEC fixture; must fall back to snapshot.
        {
            "ticker": "MSFT",
            "as_of_date": "2026-04-30",
            "watchlist_effective_trade_date": "2026-04-30",
            "primary_expectation_positive": True,
            "pead_status": "missing_last_earnings_date",
        },
    ]
    enriched = enrich_watchlist_rows(rows, sec_index, snapshot_index=snap_index)
    assert enriched[0]["last_earnings_date"] == "2026-04-30"
    assert enriched[0]["last_earnings_lookup"]["source"] == "sec_filing_features"
    assert enriched[1]["last_earnings_date"] == "2026-04-25"
    assert (
        enriched[1]["last_earnings_lookup"]["source"]
        == "earnings_snapshot_next_earnings_date"
    )


def test_pead_readiness_reprobe_assigns_buckets_correctly():
    enriched = [
        # Primary positive, inside window, residual leader -> eligible_residual.
        {
            "primary_expectation_positive": True,
            "watchlist_effective_trade_date": "2026-05-10",
            "last_earnings_date": "2026-05-05",
            "pead_window": True,
            "residual_leader": True,
            "forward_outcomes": {
                "5d": {"closed": True},
                "10d": {"closed": True},
            },
        },
        # Primary positive, inside window, not residual -> eligible_non_residual.
        {
            "primary_expectation_positive": True,
            "watchlist_effective_trade_date": "2026-05-10",
            "last_earnings_date": "2026-05-05",
            "pead_window": True,
            "residual_leader": False,
            "forward_outcomes": {"5d": {"closed": True}, "10d": {"closed": False}},
        },
        # Primary positive, outside window -> blocked_outside.
        {
            "primary_expectation_positive": True,
            "watchlist_effective_trade_date": "2026-05-10",
            "last_earnings_date": "2026-04-01",
            "pead_window": False,
            "residual_leader": True,
            "forward_outcomes": {},
        },
        # Primary positive, missing earnings date -> blocked_missing.
        {
            "primary_expectation_positive": True,
            "watchlist_effective_trade_date": "2026-05-10",
            "last_earnings_date": None,
            "pead_window": False,
            "residual_leader": False,
        },
        # Not primary -> not_primary bucket.
        {"primary_expectation_positive": False},
    ]
    out = pead_readiness_reprobe(enriched)
    assert out["bucket_counts"]["eligible_t2_t15_primary_residual"] == 1
    assert out["bucket_counts"]["eligible_t2_t15_primary_non_residual"] == 1
    assert out["bucket_counts"]["blocked_outside_t2_t15_after_earnings"] == 1
    assert out["bucket_counts"]["blocked_missing_last_earnings_date"] == 1
    assert out["bucket_counts"]["not_primary_7d_positive"] == 1
    eligible_res = out["closed_outcomes_per_eligible_bucket"][
        "eligible_t2_t15_primary_residual"
    ]
    assert eligible_res["row_count"] == 1
    assert eligible_res["closed_outcomes_by_horizon"]["5d"] == 1
    assert eligible_res["closed_outcomes_by_horizon"]["10d"] == 1


def test_build_index_respects_max_as_of(snapshot_dir):
    """``max_as_of`` is a performance trim: snapshots dated after it must not
    enter the index. Correctness of lookups *within* the kept window is
    unchanged, because PIT confirmation only requires a snapshot dated
    ``<= as_of`` whose ``next_earnings_date`` is also ``<= as_of`` — both
    derivable from earlier snapshots."""
    index_capped = build_pit_earnings_index(snapshot_dir, max_as_of="2026-04-26")
    aapl_pairs = index_capped.get("AAPL", [])
    # The 2026-05-02 snapshot must not contribute.
    assert all(snap <= "2026-04-26" for snap, _ in aapl_pairs)
    # A query asking about 2026-05-05 still resolves AAPL's last earnings as
    # 2026-05-01: the 2026-04-01 snapshot already announced that as the
    # next earnings, and calendar time alone confirms it has passed by
    # 2026-05-05. This documents that the cap is a perf optimisation and
    # does not lose information for queries within the kept window.
    result = last_earnings_date_pit("AAPL", "2026-05-05", index_capped)
    assert result["last_earnings_date"] == "2026-05-01"
    # But a query strictly beyond the cap that needs information *only*
    # available in a post-cap snapshot would lose it. Here AAPL's 2026-07-30
    # next earnings was only visible from the 2026-05-02 snapshot onwards;
    # capping at 2026-04-26 means a 2026-08-01 query cannot recover it.
    result_future = last_earnings_date_pit("AAPL", "2026-08-01", index_capped)
    assert result_future["last_earnings_date"] == "2026-05-01"  # still the older one
